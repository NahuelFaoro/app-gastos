"""Regresiones con geometría e interacción real de Qt sobre datos temporales."""
import os
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import Qt, QPoint, QPointF, QMimeData
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from app.db import Database
from app.pages.categories import CategoriesPage
from app.pages.category_tiles import MIME_CATEGORY
from app.pages.statistics import AnalysisCategoryRow
from app.pages.flex import FlexZoneCard
from app.pages.viajes_dialogs import ExtraDialog
from app.qt_runtime import normalize_application_font
from app.theme import build_palette, build_stylesheet


class RequestedUiRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        normalize_application_font(cls.app)
        cls.app.setPalette(build_palette("dark_mint"))
        cls.app.setStyleSheet(build_stylesheet("dark_mint"))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Database(Path(self.tmp.name) / "ui.db")
        self.db.initialize()
        self.widgets = []
        self.addCleanup(self.close_widgets)

    def close_widgets(self):
        for widget in self.widgets:
            widget.close()
            widget.deleteLater()
        self.app.processEvents()

    def display(self, widget, width, height):
        if widget not in self.widgets:
            self.widgets.append(widget)
        widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        widget.resize(width, height)
        widget.show()
        for _ in range(4):
            self.app.processEvents()
        return widget

    def capture(self, widget, name):
        folder = os.getenv("APPGASTOS_UI_CAPTURE")
        if folder:
            target = Path(folder)
            target.mkdir(parents=True, exist_ok=True)
            widget.grab().save(str(target / f"{name}.png"))

    def test_analysis_reflows_and_centers_on_real_card(self):
        row = AnalysisCategoryRow({"category_id": 1, "category": "Salud / Médicos", "icon": "health"},
                                  49, "$ 1.234.567,89", narrow=True)
        for width in (420, 1500, 800, 420, 1500):
            self.display(row, width, 110 if width < 720 else 80)
            if width >= 720:
                center = row._percent.mapTo(row, row._percent.rect().center())
                self.assertLessEqual(abs(center.x() - row.rect().center().x()), 2)
                self.assertLessEqual(abs(center.y() - row._amount.mapTo(row, row._amount.rect().center()).y()), 2)
                right = row._amount.mapTo(row, row._amount.rect().topRight()).x()
                self.assertGreater(right, width - 100)
            else:
                self.assertGreater(row._percent.mapTo(row, QPoint()).y(), row._left.y())
            self.capture(row, f"analysis-{width}")

    def test_flex_values_stay_aligned_as_numbers_grow(self):
        positions = []
        for quantity, total in ((0, 0), (123, 1234567.89)):
            card = self.display(FlexZoneCard(dict(id=1, name="Zona 1", quantity=quantity,
                                                 total=total, current_price=4990), "$"), 450, 240)
            count = card.findChild(QLabel, "FlexZoneCount")
            subtotal = card.findChild(QLabel, "FlexZoneSubtotal")
            positions.append(count.mapTo(card, count.rect().center()).x())
            self.assertLess(count.mapTo(card, count.rect().topRight()).x(), subtotal.mapTo(card, QPoint()).x())
            self.capture(card, f"flex-{quantity}")
        self.assertLessEqual(abs(positions[0] - positions[1]), 2)

    def test_extra_orders_accepts_keyboard_and_roundtrips(self):
        dialog = self.display(ExtraDialog(self.db), 540, 760)
        dialog.orders.setFocus()
        dialog.orders.selectAll()
        QTest.keyClicks(dialog.orders, "27")
        QTest.keyClick(dialog.orders, Qt.Key.Key_Tab)
        self.assertEqual(dialog.values()["orders"], 27)
        data = {**dialog.values(), "app_name": "Demo", "amount": 100}
        extra_id = self.db.add_work_extra(data)
        self.assertGreater(extra_id, 0)
        self.capture(dialog, "extra")

    def test_inline_panels_and_lift_preserve_context_and_data(self):
        rows = self.db.categories("expense")
        parent = next(row for row in rows if row.get("parent_id") is None)
        child = self.db.add_category("Prueba carpeta", "expense", parent["id"], "#8877EE", "other")
        leaf = self.db.add_category("Prueba interior", "expense", child, "#8877EE", "other")
        tx = self.db.add_transaction(dict(kind="expense", amount=10, account_id=self.db.accounts()[0]["id"],
                                          category_id=leaf, tx_date="2026-09-13"))
        page = self.display(CategoriesPage(self.db), 1500, 900)
        root_count = len(page._tiles)
        panel = next(panel for panel in page._tiles if child in panel.rows)
        self.assertFalse(panel.rows[child].isHidden())
        self.assertTrue(panel.rows[leaf].isHidden())
        panel.toggle(child)
        self.app.processEvents()
        self.assertFalse(panel.rows[leaf].isHidden())
        self.assertEqual(len(page._tiles), root_count)
        # Abrir y cerrar una rama conserva los mismos widgets de las demás.
        other = next(p for p in page._tiles if p is not panel)
        panel.toggle(child)
        self.assertIn(other, page._tiles)
        panel.toggle(child)
        for width in (1500, 768, 430, 1500):
            self.display(page, width, 900)
            self.assertEqual(page.scroll.horizontalScrollBar().maximum(), 0)
            self.capture(page, f"categories-inline-{width}")
        # Sacar un nivel mediante el botón visible, sin navegar.
        category_count = len(self.db.categories())
        QTest.mouseClick(panel.rows[leaf].lift_button, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertEqual(self.db.category(leaf)["parent_id"], parent["id"])
        self.assertEqual(self.db.transaction(tx)["category_id"], leaf)
        self.assertEqual(len(self.db.categories()), category_count)
        self.assertEqual(sum(leaf in p.rows for p in page._tiles), 1)
        panel = next(panel for panel in page._tiles if child in panel.rows)
        target = panel.rows[child]
        mime = QMimeData(); mime.setData(MIME_CATEGORY, str(leaf).encode())
        QApplication.sendEvent(target, QDragEnterEvent(QPoint(5, 5), Qt.DropAction.MoveAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
        QApplication.sendEvent(target, QDropEvent(QPointF(5, 5), Qt.DropAction.MoveAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
        self.app.processEvents()
        self.assertEqual(self.db.category(leaf)["parent_id"], child)
        page.search.setText("Prueba interior")
        page._search_timer.stop()
        page.refresh()
        panel = page._tiles[0]
        self.assertFalse(panel.rows[leaf].isHidden())
        self.assertIn(parent["id"], panel.rows)
        page.search.clear()
        page._search_timer.stop()
        page.refresh()
        self.assertEqual(len(page._tiles), root_count)

    def test_move_undo_and_stale_undo_preserve_data(self):
        root = self.db.add_category("Grupo prueba", "expense", None, "#8877EE", "other")
        leaf = self.db.add_category("Elemento prueba", "expense", root, "#8877EE", "other")
        tx = self.db.add_transaction(dict(kind="expense", amount=10, account_id=self.db.accounts()[0]["id"],
                                          category_id=leaf, tx_date="2026-09-13"))
        page = self.display(CategoriesPage(self.db), 1500, 900)
        panel = next(p for p in page._tiles if leaf in p.rows)
        self.assertEqual(panel.rows[leaf].lift_button.toolTip(), "Mover a categorías principales")
        QTest.mouseClick(panel.rows[leaf].lift_button, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertIsNone(self.db.category(leaf)["parent_id"])
        self.assertFalse(page.move_notice.isHidden())
        QTest.mouseClick(page.undo_button, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertEqual(self.db.category(leaf)["parent_id"], root)
        self.assertEqual(self.db.transaction(tx)["category_id"], leaf)
        self.assertEqual(sum(leaf in p.rows for p in page._tiles), 1)
        page.move_category(leaf, 0)
        self.db.move_category(leaf, root)
        page.undo_move()
        self.assertEqual(self.db.category(leaf)["parent_id"], root)
        self.assertIn("No se pudo deshacer", page.move_message.text())
        self.assertTrue(page.undo_button.isHidden())
        self.capture(page, "categories-undo")
