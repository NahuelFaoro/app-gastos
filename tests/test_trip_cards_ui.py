"""Interacción de viajes contra una base temporal, sin datos personales."""
import tempfile
import unittest
from datetime import date
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QScrollArea, QTableWidget
from app.db import Database
from app.pages.viajes import ViajesPage
from app.theme import build_palette, build_stylesheet


class TripCardsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setPalette(build_palette("dark_violet"))
        cls.app.setStyleSheet(build_stylesheet("dark_violet"))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "test.db")
        self.db.initialize()
        self.custom = self.db.save_work_field_definition({"label": "Entregado", "field_type": "check"})
        self.trip_id = self.db.add_work_trip({
            "client": "Cliente demo", "origin": "Olivos", "trip_date": "2026-09-07",
            "destinations": ["Retiro", "Palermo", "Belgrano"], "stop_count": 3,
            "charged": 30000, "details": "Conservar detalle", "flex": True,
            "custom_fields": {self.custom: False},
        })
        self.page = ViajesPage(self.db)
        self.page.current_week = date(2026, 9, 7)
        self.page.refresh()
        self.page.resize(1200, 1000)
        self.page.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.page.show()
        self.day().set_expanded(True)
        self.app.processEvents()

    def tearDown(self):
        self.page.close()
        self.page.deleteLater()
        self.app.processEvents()
        self.temp.cleanup()

    def day(self):
        return self.page.trips_tree._cards["2026-09-07"]

    def test_checks_persist_without_losing_trip_data(self):
        flex_id = next(d["id"] for d in self.db.work_field_definitions() if d.get("built_in_key") == "flex")
        self.day()._compact_cards[0].checks[flex_id].click()
        self.app.processEvents()
        self.assertFalse(self.db.work_trip(self.trip_id)["flex"])
        self.assertTrue(self.day().is_expanded())
        self.day()._compact_cards[0].checks[self.custom].click()
        self.app.processEvents()
        saved = self.db.work_trip(self.trip_id)
        self.assertTrue(saved["custom_fields"][self.custom])
        self.assertEqual(saved["destinations"], ["Retiro", "Palermo", "Belgrano"])
        self.assertEqual(saved["charged"], 30000)
        self.assertEqual(saved["details"], "Conservar detalle")
        self.assertEqual(len(self.db.work_trips_for_week("2026-09-07")), 1)
        self.assertEqual(self.db.work_week_summary("2026-09-07")["flex"], 0)

    def test_card_actions_and_single_scroll(self):
        view = self.page.trips_tree
        self.assertEqual(len(view.findChildren(QScrollArea)), 1)
        self.assertEqual(view.findChildren(QTableWidget), [])
        card = self.day()._compact_cards[0]
        QTest.mouseClick(card, Qt.MouseButton.LeftButton)
        self.assertEqual(view.selected_trip_id(), self.trip_id)
        QTest.mouseClick(card, Qt.MouseButton.LeftButton)
        self.assertIsNone(view.selected_trip_id())
        # Desconectar el diálogo modal y comprobar el destino de la acción.
        view.tripDoubleClicked.disconnect()
        edited = []
        view.tripDoubleClicked.connect(edited.append)
        card.edit_button.click()
        self.assertEqual(edited, [self.trip_id])
        for width in (1200, 620):
            view.resize(width, 750)
            self.app.processEvents()
            for check in card.checks.values():
                self.assertGreater(check.height(), 0)
                self.assertTrue(check.parentWidget().rect().contains(check.geometry()))


if __name__ == "__main__":
    unittest.main()
