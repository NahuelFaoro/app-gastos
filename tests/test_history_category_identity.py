"""El historial mantiene la identidad de categorías reorganizadas al reabrir."""
import tempfile
import unittest
from pathlib import Path

from app.db import Database


class HistoryCategoryIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Database(Path(self.tmp.name) / "history.db")
        self.db.initialize()
        with self.db.connect() as con:
            self.import_id = con.execute(
                "INSERT INTO historical_imports(file_name,file_hash) VALUES('test','test')"
            ).lastrowid

    def add_history(self, category_id=None):
        with self.db.connect() as con:
            return con.execute(
                "INSERT INTO historical_monthly(import_id,kind,year,month,category_name,"
                "subcategory_name,category_id,amount) VALUES(?,'expense',2026,1,?,?,?,123)",
                (self.import_id, "Origen prueba", "Servicio prueba", category_id),
            ).lastrowid

    def test_reopening_preserves_moved_and_renamed_category(self):
        root = self.db.add_category("Origen prueba", "expense", None, "#8877EE", "other")
        child = self.db.add_category("Servicio prueba", "expense", root, "#8877EE", "other")
        history_id = self.add_history(child)
        before = len(self.db.categories())
        self.db.move_category(child, None)
        self.db.update_category(child, "Servicio renombrado", "expense", None, "#8877EE", "other")
        for _ in range(2):
            self.db.initialize()
            self.assertEqual(len(self.db.categories()), before)
            self.assertIsNone(self.db.category(child)["parent_id"])
            self.assertEqual(self.db.category(child)["name"], "Servicio renombrado")
            with self.db.connect() as con:
                row = con.execute("SELECT category_id,amount FROM historical_monthly WHERE id=?", (history_id,)).fetchone()
                self.assertEqual(tuple(row), (child, 123))

    def test_unlinked_legacy_history_is_still_linked_once(self):
        history_id = self.add_history()
        # Simula una base anterior a la migración versionada.
        with self.db.connect() as con:
            con.execute("DELETE FROM data_migrations")
        self.db.initialize()
        with self.db.connect() as con:
            category_id = con.execute("SELECT category_id FROM historical_monthly WHERE id=?", (history_id,)).fetchone()[0]
        self.assertEqual(self.db.category(category_id)["name"], "Servicio prueba")
        before = len(self.db.categories())
        self.db.initialize()
        self.assertEqual(len(self.db.categories()), before)

    def test_startup_does_not_repeat_import_linking(self):
        history_id = self.add_history()
        before = len(self.db.categories())
        self.db.initialize()
        self.assertEqual(len(self.db.categories()), before)
        with self.db.connect() as con:
            self.assertIsNone(con.execute("SELECT category_id FROM historical_monthly WHERE id=?", (history_id,)).fetchone()[0])
        self.db.sync_legacy_categories({})
        with self.db.connect() as con:
            self.assertIsNotNone(con.execute("SELECT category_id FROM historical_monthly WHERE id=?", (history_id,)).fetchone()[0])
