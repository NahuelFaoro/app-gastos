from __future__ import annotations

from datetime import date


class FlexRepositoryMixin:
    """Persistencia del dominio Zonas/Flex."""

    def flex_zones(self, on_date: str | None = None, include_inactive: bool = False):
        target = str(on_date or date.today().isoformat())[:10]
        where = "" if include_inactive else "WHERE z.active=1"
        with self.connect() as con:
            rows = con.execute(
                f"""
                SELECT z.*,
                       COALESCE((
                           SELECT r.price
                           FROM flex_zone_rates r
                           WHERE r.zone_id=z.id AND date(r.effective_from)<=date(?)
                           ORDER BY date(r.effective_from) DESC, r.id DESC
                           LIMIT 1
                       ), (
                           SELECT r2.price
                           FROM flex_zone_rates r2
                           WHERE r2.zone_id=z.id
                           ORDER BY date(r2.effective_from) ASC, r2.id ASC
                           LIMIT 1
                       ), 0) AS current_price
                FROM flex_zones z
                {where}
                ORDER BY z.sort_order, z.id
                """,
                (target,),
            ).fetchall()
        return self._rows(rows)

    def flex_zone(self, zone_id: int, on_date: str | None = None):
        return next((z for z in self.flex_zones(on_date, True) if int(z["id"]) == int(zone_id)), None)

    def add_flex_zone(self, name: str, price: float, effective_from: str, color: str = "#4CCFA9") -> int:
        name = (name or "").strip()
        if not name:
            raise ValueError("Ingresá un nombre para la zona.")
        if float(price) < 0:
            raise ValueError("La tarifa no puede ser negativa.")
        with self.connect() as con:
            order = int(con.execute("SELECT COALESCE(MAX(sort_order),-1)+1 FROM flex_zones").fetchone()[0])
            cur = con.execute(
                "INSERT INTO flex_zones(name,color,active,sort_order) VALUES(?,?,1,?)",
                (name, color, order),
            )
            zone_id = int(cur.lastrowid)
            con.execute(
                "INSERT INTO flex_zone_rates(zone_id,price,effective_from) VALUES(?,?,?)",
                (zone_id, float(price), str(effective_from)[:10]),
            )
        return zone_id

    def update_flex_zone(self, zone_id: int, name: str, active: bool):
        name = (name or "").strip()
        if not name:
            raise ValueError("Ingresá un nombre para la zona.")
        with self.connect() as con:
            con.execute(
                "UPDATE flex_zones SET name=?,active=? WHERE id=?",
                (name, 1 if active else 0, int(zone_id)),
            )

    def flex_zone_delivery_count(self, zone_id: int) -> int:
        """Cantidad de entregas históricas asociadas a una zona."""
        with self.connect() as con:
            row = con.execute(
                "SELECT COUNT(*) AS total FROM flex_deliveries WHERE zone_id=?",
                (int(zone_id),),
            ).fetchone()
        return int(row["total"] or 0) if row else 0

    def delete_flex_zone(self, zone_id: int) -> None:
        """Elimina una zona sólo si no tiene entregas históricas.

        Las tarifas dependen de la zona con ON DELETE CASCADE. Las entregas, en
        cambio, se conservan siempre; si existen se exige desactivar la zona.
        """
        zone_id = int(zone_id)
        if self.flex_zone_delivery_count(zone_id):
            raise ValueError("La zona tiene entregas históricas. Desactivala para conservar esos registros.")
        with self.connect() as con:
            con.execute("DELETE FROM flex_zones WHERE id=?", (zone_id,))

    def reorder_flex_zones(self, ordered_ids: list[int]) -> None:
        """Persiste el orden visual definido por el usuario."""
        with self.connect() as con:
            for order, zone_id in enumerate(ordered_ids):
                con.execute("UPDATE flex_zones SET sort_order=? WHERE id=?", (order, int(zone_id)))

    def set_flex_zone_rate(self, zone_id: int, price: float, effective_from: str):
        """Define una tarifa *desde* una fecha y conserva correctamente el pasado.

        Flex es un esquema de tarifas por vigencia: cuando el usuario dice que
        Zona 1 vale X desde una fecha, ese precio debe gobernar desde ese día
        hacia adelante. Las versiones anteriores solamente insertaban una fila
        adicional; si había una tarifa posterior (incluida la tarifa inicial
        sembrada al crear la app), esa fila posterior volvía a imponerse y daba
        la sensación de que cambiar fecha/precio no hacía nada.

        Antes de reemplazar cambios posteriores preservamos la tarifa anterior
        como línea base cuando todavía no existía una fila previa. De ese modo
        las semanas viejas siguen mostrando el precio viejo y las nuevas toman
        el nuevo.
        """
        price = float(price)
        if price < 0:
            raise ValueError("La tarifa no puede ser negativa.")
        zone_id = int(zone_id)
        effective = str(effective_from)[:10]
        with self.connect() as con:
            # Precio que regía inmediatamente antes de la nueva vigencia.
            previous = con.execute(
                """
                SELECT price FROM flex_zone_rates
                WHERE zone_id=? AND date(effective_from)<date(?)
                ORDER BY date(effective_from) DESC,id DESC LIMIT 1
                """,
                (zone_id, effective),
            ).fetchone()

            # Si nunca hubo una fila anterior, la implementación vieja usaba la
            # primera tarifa futura como fallback. La conservamos como baseline
            # antes de eliminarla, para que el historial previo no cambie.
            if previous is None:
                fallback = con.execute(
                    """
                    SELECT price FROM flex_zone_rates
                    WHERE zone_id=?
                    ORDER BY date(effective_from) ASC,id ASC LIMIT 1
                    """,
                    (zone_id,),
                ).fetchone()
                if fallback is not None:
                    baseline_exists = con.execute(
                        "SELECT 1 FROM flex_zone_rates WHERE zone_id=? AND effective_from='2000-01-01'",
                        (zone_id,),
                    ).fetchone()
                    if not baseline_exists:
                        con.execute(
                            "INSERT INTO flex_zone_rates(zone_id,price,effective_from) VALUES(?,?,?)",
                            (zone_id, float(fallback[0]), "2000-01-01"),
                        )

            # 'Desde' significa que cualquier cambio posterior que hubiese
            # quedado cargado deja de aplicar. Si después se quiere programar
            # otro aumento, se agrega normalmente con una fecha posterior.
            con.execute(
                "DELETE FROM flex_zone_rates WHERE zone_id=? AND date(effective_from)>=date(?)",
                (zone_id, effective),
            )
            con.execute(
                "INSERT INTO flex_zone_rates(zone_id,price,effective_from) VALUES(?,?,?)",
                (zone_id, price, effective),
            )

    def flex_rate_history(self, zone_id: int):
        with self.connect() as con:
            rows = con.execute(
                "SELECT * FROM flex_zone_rates WHERE zone_id=? ORDER BY date(effective_from) DESC,id DESC",
                (int(zone_id),),
            ).fetchall()
        return self._rows(rows)

    def add_flex_delivery(self, zone_id: int, week_start: str, quantity: int = 1, rate_date: str | None = None) -> int:
        quantity = max(1, int(quantity or 1))
        zone = self.flex_zone(int(zone_id), rate_date or date.today().isoformat())
        if not zone:
            raise ValueError("La zona ya no existe.")
        price = float(zone.get("current_price") or 0)
        with self.connect() as con:
            cur = con.execute(
                "INSERT INTO flex_deliveries(zone_id,week_start,quantity,unit_price) VALUES(?,?,?,?)",
                (int(zone_id), str(week_start)[:10], quantity, price),
            )
            return int(cur.lastrowid)

    def delete_flex_delivery(self, delivery_id: int):
        with self.connect() as con:
            con.execute("DELETE FROM flex_deliveries WHERE id=?", (int(delivery_id),))

    def remove_last_flex_delivery(self, zone_id: int, week_start: str) -> bool:
        with self.connect() as con:
            row = con.execute(
                """
                SELECT * FROM flex_deliveries
                WHERE zone_id=? AND week_start=?
                ORDER BY id DESC LIMIT 1
                """,
                (int(zone_id), str(week_start)[:10]),
            ).fetchone()
            if not row:
                return False
            if int(row["quantity"] or 1) > 1:
                con.execute("UPDATE flex_deliveries SET quantity=quantity-1 WHERE id=?", (row["id"],))
            else:
                con.execute("DELETE FROM flex_deliveries WHERE id=?", (row["id"],))
        return True

    def flex_week_summary(self, week_start: str):
        week_start = str(week_start)[:10]
        zones = {int(z["id"]): z for z in self.flex_zones(week_start, True)}
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT zone_id,
                       COALESCE(SUM(quantity),0) AS quantity,
                       COALESCE(SUM(quantity*unit_price),0) AS total,
                       COALESCE(SUM(quantity*unit_price)/NULLIF(SUM(quantity),0),0) AS average_price
                FROM flex_deliveries
                WHERE week_start=?
                GROUP BY zone_id
                """,
                (week_start,),
            ).fetchall()
        grouped = {int(r["zone_id"]): dict(r) for r in rows}
        items = []
        for zone_id, zone in zones.items():
            data = grouped.get(zone_id, {})
            quantity = int(data.get("quantity") or 0)
            if not bool(zone.get("active", 1)) and quantity <= 0:
                continue
            items.append({
                **zone,
                "quantity": quantity,
                "total": float(data.get("total") or 0),
                "average_price": float(data.get("average_price") or zone.get("current_price") or 0),
            })
        total_qty = sum(int(x["quantity"]) for x in items)
        total_amount = sum(float(x["total"]) for x in items)
        return {
            "week_start": week_start,
            "zones": items,
            "quantity": total_qty,
            "total": total_amount,
            "average": (total_amount / total_qty) if total_qty else 0.0,
        }

    def flex_week_history(self, limit: int = 10):
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT week_start,
                       COALESCE(SUM(quantity),0) AS quantity,
                       COALESCE(SUM(quantity*unit_price),0) AS total
                FROM flex_deliveries
                GROUP BY week_start
                ORDER BY date(week_start) DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return self._rows(rows)

    def flex_deliveries_rows(self):
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT d.*, z.name AS zone_name, z.color AS zone_color
                FROM flex_deliveries d
                JOIN flex_zones z ON z.id=d.zone_id
                ORDER BY date(d.week_start) DESC, d.id DESC
                """
            ).fetchall()
        return self._rows(rows)

    def flex_rates_rows(self):
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT r.*, z.name AS zone_name
                FROM flex_zone_rates r
                JOIN flex_zones z ON z.id=r.zone_id
                ORDER BY z.sort_order, z.id, date(r.effective_from) DESC, r.id DESC
                """
            ).fetchall()
        return self._rows(rows)

    def flex_income_link(self, week_start: str):
        with self.connect() as con:
            row = con.execute(
                """
                SELECT l.*, t.id AS existing_transaction_id
                FROM flex_income_links l
                LEFT JOIN transactions t ON t.id=l.transaction_id
                WHERE l.week_start=?
                """,
                (str(week_start)[:10],),
            ).fetchone()
        return dict(row) if row else None

    def set_flex_income_link(self, week_start: str, transaction_id: int, amount: float):
        with self.connect() as con:
            con.execute(
                """
                INSERT INTO flex_income_links(week_start,transaction_id,amount)
                VALUES(?,?,?)
                ON CONFLICT(week_start)
                DO UPDATE SET transaction_id=excluded.transaction_id,amount=excluded.amount,created_at=CURRENT_TIMESTAMP
                """,
                (str(week_start)[:10], int(transaction_id), float(amount)),
            )
