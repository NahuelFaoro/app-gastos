"""Auditoría de geometría con datos ficticios, en píxeles lógicos de Qt."""
import tempfile
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from app.db import Database
from app.main_window import MainWindow
from scripts.check_app import seed


def main():
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as folder:
        db = Database(Path(folder) / "responsive.db")
        db.initialize()
        seed(db)
        window = MainWindow(db)
        window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        window.show()
        for width, height in ((1920, 1080), (1366, 768), (760, 1100), (560, 600), (480, 360)):
            window.resize(width, height)
            QTest.qWait(40)
            assert window.width() <= width and window.height() <= height, (width, height, window.size())
            for key in window.page_index:
                window.select_page(window.page_index[key])
                QTest.qWait(15)
                assert window.stack.geometry().right() < window.width(), key
            window.select_page(window.page_index["tools"])
            window.tools.open_viajes()
            QTest.qWait(40)
            page = window.tools.viajes
            cards = page._metric_cards()
            for i, left in enumerate(cards):
                for right in cards[i+1:]:
                    assert not left.geometry().intersects(right.geometry()), (width, left.geometry(), right.geometry())
                assert page.stats_host.rect().contains(left.geometry()), (width, left.geometry(), page.stats_host.rect())
            Path("build").mkdir(exist_ok=True)
            window.grab().save(f"build/responsive-{width}-{height}.png")
            print(f"{width}x{height}: páginas accesibles y métricas sin superposición")
        window.close()
        window.deleteLater()
        app.processEvents()
    print("APP_GASTOS_RESPONSIVE_OK")


if __name__ == "__main__":
    main()
