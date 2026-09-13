from __future__ import annotations

import os
import sqlite3
import json
import re
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any

from .constants import CATEGORY_COLORS, CATEGORY_ICON_BY_NAME, EXPENSE_CATEGORIES, INCOME_CATEGORIES
from .icon_data import LEGACY_ICON_MAP, normalize_icon
from .work_calendar import week_start_iso
from .repositories.accounts import AccountsMixin
from .repositories.installments import InstallmentsMixin
from .repositories.transactions import TransactionsMixin
from .repositories.analytics import AnalyticsMixin
from .repositories.planning import PlanningMixin
from .repositories.import_queue import ImportQueueMixin
from .repositories.history import HistoryRepositoryMixin
from .repositories.categories import CategoryRepositoryMixin
from .repositories.flex import FlexRepositoryMixin
from .repositories.work_config import WorkConfigMixin
from .repositories.work_tracking import WorkTrackingMixin
from .schema import BASE_SCHEMA_SQL


class Database(AccountsMixin, InstallmentsMixin, TransactionsMixin, AnalyticsMixin, PlanningMixin, ImportQueueMixin, HistoryRepositoryMixin, CategoryRepositoryMixin, WorkTrackingMixin, FlexRepositoryMixin, WorkConfigMixin):
    def __init__(self, path: str | Path | None = None):
        if path is None:
            base = Path(os.getenv("APPDATA") or (Path.home() / ".app_gastos"))
            data_dir = (base / "AppGastos") if os.getenv("APPDATA") else base
            data_dir.mkdir(parents=True, exist_ok=True)
            path = data_dir / "app_gastos.db"
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._settings_cache: dict[str, str] = {}
        # Privacidad de sesión: no se persiste. Sirve para compartir pantalla o
        # mostrar la app sin exponer importes reales.
        self._privacy_mode = False

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        # WAL es persistente en el archivo y se configura una vez en initialize.
        # Ejecutar PRAGMA journal_mode en cada lectura agregaba latencia evitable.
        con.execute("PRAGMA busy_timeout = 3000")
        con.execute("PRAGMA synchronous = NORMAL")
        con.execute("PRAGMA temp_store = MEMORY")
        con.execute("PRAGMA cache_size = -12000")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    @staticmethod
    def _rows(rows) -> list[dict[str, Any]]:
        return [dict(r) for r in rows]

    @staticmethod
    def _columns(con: sqlite3.Connection, table: str) -> set[str]:
        return {r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}

    def _ensure_column(self, con: sqlite3.Connection, table: str, name: str, declaration: str):
        if name not in self._columns(con, table):
            con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")

    def initialize(self) -> None:
        """Crea/actualiza el esquema y deja la base lista para usar.

        La coordinación queda deliberadamente corta: cada bloque de migración o
        seed tiene una responsabilidad aislada para que agregar una versión de
        datos no obligue a tocar el resto del arranque.
        """
        self._settings_cache.clear()
        with self.connect() as con:
            con.execute("PRAGMA journal_mode = WAL")
            con.executescript(BASE_SCHEMA_SQL)
            self._apply_column_migrations(con)
            self._seed_core_data(con)
            self._normalize_category_icons(con)
            self._seed_flex_defaults(con)
            self._ensure_default_settings(con)
            self._run_work_tracking_migrations(con)
            self._link_existing_history_categories(con)
            self._reload_settings_cache(con)
            con.execute("PRAGMA optimize")

        # Este backfill usa helpers que abren su propia conexión SQLite y por eso
        # debe ejecutarse fuera de la transacción principal de initialize().
        self._backfill_scanned_installments()

    def _apply_column_migrations(self, con: sqlite3.Connection) -> None:
        """Agrega columnas/índices introducidos por versiones anteriores.

        Todas las operaciones son idempotentes: initialize() puede ejecutarse
        en cada arranque sin duplicar ni pisar datos del usuario.
        """
        columns = (
            ("accounts", "color", "TEXT NOT NULL DEFAULT '#4CCFA9'"),
            ("accounts", "archived", "INTEGER NOT NULL DEFAULT 0"),
            ("accounts", "include_in_balance", "INTEGER NOT NULL DEFAULT 1"),
            ("accounts", "credit_limit", "REAL NOT NULL DEFAULT 0"),
            ("accounts", "closing_day", "INTEGER"),
            ("accounts", "due_day", "INTEGER"),
            ("categories", "icon", "TEXT NOT NULL DEFAULT 'other'"),
            ("categories", "secondary_color", "TEXT"),
            ("categories", "sort_order", "INTEGER NOT NULL DEFAULT 0"),
            ("transactions", "description", "TEXT NOT NULL DEFAULT ''"),
            ("transactions", "tags", "TEXT NOT NULL DEFAULT ''"),
            ("transactions", "recurring_id", "INTEGER"),
            ("transactions", "updated_at", "TEXT NOT NULL DEFAULT ''"),
            ("transactions", "source", "TEXT NOT NULL DEFAULT 'manual'"),
            ("transactions", "external_id", "TEXT"),
            ("transactions", "installment_plan_id", "INTEGER"),
            ("transactions", "installment_number", "INTEGER"),
            ("transactions", "installment_total", "INTEGER"),
            ("work_trips", "flex", "INTEGER NOT NULL DEFAULT 0"),
            ("work_trips", "trip_count", "INTEGER NOT NULL DEFAULT 1 CHECK(trip_count > 0)"),
            ("work_trips", "stop_count", "INTEGER NOT NULL DEFAULT 1 CHECK(stop_count > 0)"),
            ("work_trips", "own_client", "INTEGER NOT NULL DEFAULT 0"),
            ("work_trips", "rate_scheme_id", "INTEGER"),
            ("work_trips", "rate_quantity", "REAL"),
            ("work_trips", "rate_option_id", "INTEGER"),
            ("work_trips", "calculated_price", "REAL"),
            ("work_rate_options", "active", "INTEGER NOT NULL DEFAULT 1"),
            ("work_field_definitions", "ui_type", "TEXT NOT NULL DEFAULT ''"),
            ("work_field_definitions", "options_json", "TEXT NOT NULL DEFAULT '[]'"),
        )
        for table, name, declaration in columns:
            self._ensure_column(con, table, name, declaration)

        con.execute("UPDATE work_field_definitions SET ui_type=field_type WHERE ui_type IS NULL OR ui_type='' ")
        con.execute("UPDATE transactions SET updated_at=created_at WHERE updated_at='' OR updated_at IS NULL")
        con.execute("UPDATE transactions SET source='manual' WHERE source IS NULL OR source=''")
        con.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_tx_source_external "
            "ON transactions(source, external_id) WHERE external_id IS NOT NULL AND external_id<>''"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_tx_installment_plan "
            "ON transactions(installment_plan_id, installment_number)"
        )

    def _seed_core_data(self, con: sqlite3.Connection) -> None:
        if con.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0:
            con.executemany(
                "INSERT INTO accounts(name,type,opening_balance,color) VALUES(?,?,?,?)",
                [
                    ("Efectivo", "Efectivo", 0, "#20A66A"),
                    ("Mercado Pago", "Billetera", 0, "#3E8EF7"),
                    ("Banco", "Banco", 0, "#4CCFA9"),
                ],
            )
        if con.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
            self._seed_categories(con, "expense", EXPENSE_CATEGORIES)
            self._seed_categories(con, "income", INCOME_CATEGORIES)

    def _normalize_category_icons(self, con: sqlite3.Connection) -> None:
        # Asigna íconos conocidos sin tocar personalizaciones válidas.
        for name, icon in CATEGORY_ICON_BY_NAME.items():
            con.execute(
                "UPDATE categories SET icon=? WHERE name=? "
                "AND (icon IS NULL OR icon='' OR icon='other')",
                (icon, name),
            )
        for legacy, icon in LEGACY_ICON_MAP.items():
            con.execute("UPDATE categories SET icon=? WHERE icon=?", (icon, legacy))
        for row in con.execute("SELECT id, name, icon FROM categories").fetchall():
            normalized = normalize_icon(row["icon"], row["name"])
            if normalized != row["icon"]:
                con.execute("UPDATE categories SET icon=? WHERE id=?", (normalized, row["id"]))

    def _seed_flex_defaults(self, con: sqlite3.Connection) -> None:
        if con.execute("SELECT COUNT(*) FROM flex_zones").fetchone()[0] != 0:
            return
        defaults = (
            ("Zona 1", "#3E8EF7", 0, 0.0),
            ("Zona 2", "#20A66A", 1, 0.0),
            ("Zona 3", "#F0A04B", 2, 0.0),
            ("Zona 4", "#E45567", 3, 0.0),
        )
        today_iso = date.today().isoformat()
        for zone_name, color, order, price in defaults:
            cur = con.execute(
                "INSERT INTO flex_zones(name,color,active,sort_order) VALUES(?,?,1,?)",
                (zone_name, color, order),
            )
            con.execute(
                "INSERT INTO flex_zone_rates(zone_id,price,effective_from) VALUES(?,?,?)",
                (cur.lastrowid, price, today_iso),
            )

    def _ensure_default_settings(self, con: sqlite3.Connection) -> None:
        defaults = {
            "theme": "dark_mint",
            "ui_scale": "1.00",
            "currency_symbol": "$",
            "hide_balances": "0",
            "last_account_id": "",
            "last_expense_category_id": "",
            "last_income_category_id": "",
            "mercadopago_account_id": "",
            "mercadopago_auto_review": "1",
            "mercadopago_last_import": "",
            "mercadopago_auto_sync": "0",
            "mercadopago_sync_days": "30",
            "mercadopago_last_api_sync": "",
            "mercadopago_last_api_sync_iso": "",
            "flex_tool_name": "Pedidos por zonas",
            "flex_item_singular": "envío",
            "flex_item_plural": "envíos",
        }
        con.executemany("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", defaults.items())

    def _run_work_tracking_migrations(self, con: sqlite3.Connection) -> None:
        self._seed_work_field_definitions(con)
        self._migrate_work_tracking_v033(con)
        self._migrate_work_tracking_v0331(con)
        self._migrate_work_tracking_v0340(con)
        self._migrate_work_tracking_v0380(con)

    def _reload_settings_cache(self, con: sqlite3.Connection) -> None:
        self._settings_cache = {
            str(row["key"]): str(row["value"])
            for row in con.execute("SELECT key,value FROM settings").fetchall()
        }

    @staticmethod
    def _work_week_start(value: str | date) -> str:
        """Compatibilidad interna: delega la regla semanal al helper compartido."""
        return week_start_iso(value)


    def _migrate_work_tracking_v033(self, con: sqlite3.Connection) -> None:
        """Normaliza los datos de trabajo creados antes de v0.33.

        La migración es deliberadamente idempotente: puede ejecutarse en cada
        arranque sin duplicar registros ni pisar ediciones posteriores.
        """
        # Marcar FLEX en viajes históricos. Solo limpiamos Detalles cuando el
        # valor era exactamente "FLEX"; textos como "FLEX + demora" se
        # conservan porque contienen información adicional.
        con.execute(
            "UPDATE work_trips SET flex=1 WHERE flex=0 AND instr(lower(details), 'flex') > 0"
        )
        # En algunas filas históricas la marca estaba en el cliente
        # ("Cliente (flex)") en lugar de Detalles. La convertimos al mismo
        # booleano y limpiamos el nombre para no mostrar la etiqueta dos veces.
        for row in con.execute(
            "SELECT id,client FROM work_trips WHERE instr(lower(client), '(flex)') > 0"
        ).fetchall():
            clean_client = re.sub(r"\s*\(\s*flex\s*\)\s*", " ", str(row["client"]), flags=re.I).strip()
            con.execute(
                "UPDATE work_trips SET client=?,flex=1 WHERE id=?",
                (clean_client, int(row["id"])),
            )
        con.execute(
            "UPDATE work_trips SET details='' WHERE upper(trim(details))='FLEX'"
        )

        marker = con.execute(
            "SELECT value FROM settings WHERE key='work_extras_migrated_v1'"
        ).fetchone()
        if marker:
            return

        legacy_rows = con.execute(
            "SELECT * FROM work_services ORDER BY id"
        ).fetchall()
        for row in legacy_rows:
            details = " · ".join(
                part for part in (
                    str(row["client"] or "").strip(),
                    str(row["location"] or "").strip(),
                    str(row["details"] or "").strip(),
                ) if part
            )
            con.execute(
                """
                INSERT INTO work_extras(app_name,work_date,week_start,hours,orders,amount,details)
                VALUES(?,?,?,?,?,?,?)
                """,
                (
                    "Otro",
                    str(row["service_date"]),
                    str(row["week_start"]),
                    0.0, 0, float(row["charged"] or 0), details,
                ),
            )
        con.execute(
            "INSERT OR REPLACE INTO settings(key,value) VALUES('work_extras_migrated_v1',?)",
            (str(len(legacy_rows)),),
        )

    def _migrate_work_tracking_v0331(self, con: sqlite3.Connection) -> None:
        """Estructura cantidades de viaje usadas previamente como texto libre.

        Antes de v0.33.1 una entrada equivalía siempre a un viaje. En la práctica
        el usuario suele agrupar varios recorridos del mismo cliente en una fila,
        especialmente FLEX, escribiendo por ejemplo ``5 Flex`` en Detalles.

        La migración se ejecuta una sola vez por base. Solo interpreta textos que
        sean inequívocamente una cantidad FLEX completa (``5 Flex`` o ``Flex 5``),
        evitando convertir números que formen parte de una observación real.
        """
        marker_key = "work_trip_count_migrated_v1"
        if con.execute("SELECT 1 FROM settings WHERE key=?", (marker_key,)).fetchone():
            return

        patterns = (
            re.compile(r"^\s*(\d+)\s*(?:x\s*)?flex\s*$", re.I),
            re.compile(r"^\s*flex\s*(?:x\s*)?(\d+)\s*$", re.I),
        )
        migrated = 0
        rows = con.execute(
            "SELECT id,details,trip_count FROM work_trips WHERE flex=1 AND trip_count=1"
        ).fetchall()
        for row in rows:
            details = str(row["details"] or "")
            match = next((pattern.match(details) for pattern in patterns if pattern.match(details)), None)
            if not match:
                continue
            quantity = max(1, int(match.group(1)))
            con.execute(
                "UPDATE work_trips SET trip_count=?,details='',updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (quantity, int(row["id"])),
            )
            migrated += 1

        con.execute(
            "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
            (marker_key, str(migrated)),
        )

    def _migrate_work_tracking_v0340(self, con: sqlite3.Connection) -> None:
        """Reconvierte la gestión de viajes a paradas por fila.

        v0.33.1 permitía que una fila sumara varios viajes reales mediante
        ``trip_count``. En la práctica resultó más útil volver a 1 fila = 1 viaje
        y usar ``stop_count`` para registrar cuántas paradas/direcciones tuvo ese
        recorrido. La migración conserva el dato histórico más rico posible:

        * si había varios destinos, ``stop_count`` pasa a ser esa cantidad;
        * si un FLEX viejo agrupaba 5 viajes, se aprovecha ese valor como
          cantidad de paradas cuando no había una estructura mejor;
        * ``trip_count`` se normaliza a 1 para que los resúmenes vuelvan a contar
          viajes por fila.
        """
        marker_key = "work_tracking_v0340"
        if con.execute("SELECT 1 FROM settings WHERE key=?", (marker_key,)).fetchone():
            return

        trip_rows = con.execute("SELECT id,trip_count,stop_count FROM work_trips").fetchall()
        migrated = 0
        for row in trip_rows:
            trip_id = int(row["id"])
            destination_count = con.execute(
                "SELECT COUNT(*) FROM work_trip_destinations WHERE trip_id=?",
                (trip_id,),
            ).fetchone()[0]
            stop_count = max(
                1,
                int(row["stop_count"] or 0),
                int(destination_count or 0),
                int(row["trip_count"] or 0),
            )
            con.execute(
                """
                UPDATE work_trips
                SET stop_count=?, trip_count=1, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (stop_count, trip_id),
            )
            migrated += 1

        con.execute(
            "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
            (marker_key, str(migrated)),
        )

    def _migrate_work_tracking_v0380(self, con: sqlite3.Connection) -> None:
        """Retira del esquema los restos del kilometraje estimado por API.

        v0.38 conserva únicamente el kilometraje real por odómetro. La limpieza
        es idempotente y también se ejecuta al restaurar backups de versiones
        anteriores.
        """
        columns = self._columns(con, "work_trips")
        for column in ("estimated_km", "estimated_duration_min", "route_provider", "route_calculated_at"):
            if column in columns:
                con.execute(f"ALTER TABLE work_trips DROP COLUMN {column}")
                columns.discard(column)
        con.execute("DROP TABLE IF EXISTS work_geocode_cache")
        con.execute("DELETE FROM settings WHERE key='routing_location_hint'")

    def _backfill_scanned_installments(self):
        try:
            with self.connect() as con:
                rows = self._rows(con.execute(
                    """
                    SELECT i.transaction_id,i.account_id,i.raw_json
                    FROM imported_movements i
                    JOIN transactions t ON t.id=i.transaction_id
                    JOIN accounts a ON a.id=i.account_id
                    WHERE i.status='imported' AND i.source='statement_scan'
                      AND i.transaction_id IS NOT NULL
                      AND a.type='Tarjeta'
                      AND t.kind='expense'
                      AND t.installment_plan_id IS NULL
                    """
                ).fetchall())
        except Exception:
            return
        for row in rows:
            try:
                raw = json.loads(row.get("raw_json") or "{}")
                current = int(raw.get("installment_current") or 0)
                total = int(raw.get("installment_total") or 0)
                if total > 1 and 1 <= current <= total:
                    self.configure_existing_installment(
                        int(row["transaction_id"]), current, total, int(row["account_id"])
                    )
            except Exception:
                continue

    def _seed_categories(self, con: sqlite3.Connection, kind: str, groups: dict[str, list[str]]):
        for i, (parent, children) in enumerate(groups.items()):
            color = CATEGORY_COLORS[i % len(CATEGORY_COLORS)]
            cur = con.execute(
                "INSERT INTO categories(name,kind,parent_id,color,icon,sort_order) VALUES(?,?,NULL,?,?,?)",
                (parent, kind, color, CATEGORY_ICON_BY_NAME.get(parent, "other"), i),
            )
            pid = cur.lastrowid
            for j, child in enumerate(children):
                con.execute(
                    "INSERT INTO categories(name,kind,parent_id,color,icon,sort_order) VALUES(?,?,?,?,?,?)",
                    (child, kind, pid, color, CATEGORY_ICON_BY_NAME.get(child, CATEGORY_ICON_BY_NAME.get(parent, "other")), j),
                )

    # ---------- settings ----------
    def get_setting(self, key: str, default: str = "") -> str:
        if key in self._settings_cache:
            return self._settings_cache[key]
        with self.connect() as con:
            row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        value = str(row[0]) if row else default
        self._settings_cache[key] = value
        return value

    def set_setting(self, key: str, value: Any):
        value = str(value)
        with self.connect() as con:
            con.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
        self._settings_cache[key] = value

    def currency_symbol(self) -> str:
        return self.get_setting("currency_symbol", "$") or "$"

    def privacy_mode(self) -> bool:
        return bool(getattr(self, "_privacy_mode", False))

    def set_privacy_mode(self, enabled: bool):
        self._privacy_mode = bool(enabled)

    def balances_hidden(self) -> bool:
        # El ajuste persistente y el modo privacidad temporal se combinan.
        return self.privacy_mode() or self.get_setting("hide_balances", "0") == "1"

    # ---------- backup / restore ----------
    def create_backup(self, destination: str | Path):
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        src = sqlite3.connect(self.path)
        dst = sqlite3.connect(destination)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()

    def restore_backup(self, source: str | Path):
        source = Path(source)
        src = sqlite3.connect(source)
        try:
            tables = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            if not {"accounts", "categories", "transactions"}.issubset(tables):
                raise ValueError("El archivo no parece ser una base válida de App Gastos.")
            dst = sqlite3.connect(self.path)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        self.initialize()
