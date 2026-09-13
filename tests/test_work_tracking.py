from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.db import Database


class WorkTrackingDatabaseTests(unittest.TestCase):
    """Pruebas de persistencia de Viajes y kilometraje real por odómetro."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tempdir.name) / "app_gastos_test.db")
        self.db.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _add_trip(self, **overrides) -> int:
        payload = {
            "client": "Cliente demo",
            "origin": "Origen demo",
            "destinations": ["Destino A", "Destino B", "Destino C"],
            "trip_date": "2026-09-07",
            "bulky": False,
            "rain": False,
            "flex": True,
            "own_client": False,
            "details": "",
            "charged": None,
        }
        payload.update(overrides)
        return self.db.add_work_trip(payload)

    def test_one_row_is_one_trip_and_destinations_are_stops(self) -> None:
        self._add_trip()
        summary = self.db.work_week_summary("2026-09-07")
        self.assertEqual(summary["trips"], 1)
        self.assertEqual(summary["stops"], 3)
        self.assertEqual(summary["flex"], 3)

    def test_own_client_is_filterable(self) -> None:
        self._add_trip(own_client=True)
        self._add_trip(client="Otro", destinations=["Retiro"], own_client=False)
        rows = self.db.work_trips_for_week("2026-09-07", flag="own_client")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["client"], "Cliente demo")

    def test_odometer_computes_real_weekly_km(self) -> None:
        self.db.set_work_day_mileage("2026-09-07", 10_000.0, 10_082.5)
        self.db.set_work_day_mileage("2026-09-08", 10_082.5, 10_151.0)
        summary = self.db.work_week_mileage_summary("2026-09-07")
        self.assertAlmostEqual(summary["real_km"], 151.0)
        self.assertEqual(summary["completed_days"], 2)

    def test_weekend_mileage_and_trips_are_part_of_same_week(self) -> None:
        self._add_trip(trip_date="2026-09-12", destinations=["Sábado"], charged=1500)
        self._add_trip(trip_date="2026-09-13", destinations=["Domingo"], charged=2500)
        self.db.set_work_day_mileage("2026-09-12", 5000, 5042)
        self.db.set_work_day_mileage("2026-09-13", 5042, 5090)

        trips = self.db.work_trips_for_week("2026-09-07")
        summary = self.db.work_week_summary("2026-09-07")
        mileage = self.db.work_week_mileage_summary("2026-09-07")
        self.assertEqual(len(trips), 2)
        self.assertEqual(summary["trips"], 2)
        self.assertEqual(summary["charged"], 4000.0)
        self.assertAlmostEqual(mileage["real_km"], 90.0)
        self.assertEqual(mileage["completed_days"], 2)

    def test_last_odometer_end_carries_across_workdays(self) -> None:
        self.db.set_work_day_mileage("2026-09-04", 1000.0, 1088.0)
        self.db.set_work_day_mileage("2026-09-07", 1088.0, 1142.0)
        self.assertEqual(self.db.work_last_odometer_end_before("2026-09-07"), 1088.0)
        self.assertEqual(self.db.work_last_odometer_end_before("2026-09-08"), 1142.0)

    def test_odometer_rejects_end_before_start(self) -> None:
        with self.assertRaises(ValueError):
            self.db.set_work_day_mileage("2026-09-07", 500.0, 499.0)

    def test_month_summary_respects_calendar_month_boundaries(self) -> None:
        self._add_trip(trip_date="2026-09-30", destinations=["A", "B"], bulky=True, charged=1000)
        self._add_trip(trip_date="2026-10-01", destinations=["C"], rain=True, charged=2000)
        self.db.set_work_day_mileage("2026-09-30", 3000, 3040)
        self.db.set_work_day_mileage("2026-10-01", 3040, 3075)

        september = self.db.work_month_summary(2026, 9)
        october = self.db.work_month_summary(2026, 10)
        self.assertEqual(september["trips"], 1)
        self.assertEqual(september["stops"], 2)
        self.assertEqual(september["bulky"], 1)
        self.assertAlmostEqual(september["real_km"], 40.0)
        self.assertEqual(september["charged"], 1000.0)
        self.assertEqual(october["trips"], 1)
        self.assertEqual(october["rain"], 1)
        self.assertAlmostEqual(october["real_km"], 35.0)
        self.assertEqual(october["charged"], 2000.0)

        weekly = self.db.work_month_week_summaries(2026, 9)
        self.assertTrue(any(row["trips"] == 1 and row["period_end"] == "2026-09-30" for row in weekly))


    def test_routing_schema_is_removed_without_losing_trip_data(self) -> None:
        path = Path(self.tempdir.name) / "legacy_routing.db"
        import sqlite3

        con = sqlite3.connect(path)
        con.executescript(
            """
            CREATE TABLE work_trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client TEXT NOT NULL DEFAULT '',
                origin TEXT NOT NULL DEFAULT '',
                trip_date TEXT NOT NULL,
                week_start TEXT NOT NULL,
                trip_count INTEGER NOT NULL DEFAULT 1,
                stop_count INTEGER NOT NULL DEFAULT 1,
                bulky INTEGER NOT NULL DEFAULT 0,
                rain INTEGER NOT NULL DEFAULT 0,
                flex INTEGER NOT NULL DEFAULT 0,
                own_client INTEGER NOT NULL DEFAULT 0,
                details TEXT NOT NULL DEFAULT '',
                charged REAL,
                estimated_km REAL,
                estimated_duration_min REAL,
                route_provider TEXT NOT NULL DEFAULT '',
                route_calculated_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE work_geocode_cache (
                query TEXT NOT NULL,
                location_hint TEXT NOT NULL DEFAULT '',
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                provider TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(query, location_hint)
            );
            INSERT INTO work_trips(
                client, origin, trip_date, week_start, stop_count, flex, charged, estimated_km
            ) VALUES('Legacy', 'Origen', '2026-09-07', '2026-09-07', 2, 1, 15000, 27.5);
            """
        )
        con.commit()
        con.close()

        migrated = Database(path)
        migrated.initialize()
        with migrated.connect() as con:
            columns = {row[1] for row in con.execute("PRAGMA table_info(work_trips)").fetchall()}
            tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        self.assertNotIn("estimated_km", columns)
        self.assertNotIn("route_provider", columns)
        self.assertNotIn("work_geocode_cache", tables)
        rows = migrated.work_trips_for_week("2026-09-07")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["client"], "Legacy")
        self.assertEqual(rows[0]["stop_count"], 2)
        self.assertEqual(rows[0]["charged"], 15000)


if __name__ == "__main__":
    unittest.main()
