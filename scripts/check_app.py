from __future__ import annotations

"""Prueba de humo de App Gastos.

Se ejecuta una vez por versión desde start.bat. Usa una base temporal y el
backend nativo de Qt: no toca los datos reales y no muestra ventanas. El test
`offscreen` fue retirado porque PySide6 6.11 ya no incluye su antigua carpeta
de fuentes interna en Windows. El objetivo sigue siendo detectar crashes de
construcción, layouts responsive y diálogos antes de abrir la aplicación.
"""

import os
import sys
import tempfile
import traceback
from datetime import date
from pathlib import Path

os.environ.setdefault("QT_SCALE_FACTOR", "1.00")

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QApplication

from app.db import Database
from app.dialogs import CategoryDialog, CategoryPickerDialog, TransactionDialog
from app.main_window import MainWindow
from app.pages.flex import FlexRatesDialog, FlexZoneCard
from app.pages.statistics import CategoryBreakdownDialog
from app.pages.viajes_dialogs import ExtraDialog, MileageWeekDialog, TripDialog
from app.date_picker import CalendarDialog
from app.pages.work_monthly import WorkMonthSummaryDialog
from app.pages.work_config import WorkCustomizationDialog
from app.theme import build_palette, build_stylesheet
from app.qt_runtime import normalize_application_font


def seed(db: Database):
    accounts = db.accounts()
    account_id = int(accounts[0]["id"])
    expense = db.category_choices("expense", include_parents=False)[0]
    income = db.category_choices("income", include_parents=False)[0]
    today = date.today().isoformat()
    db.add_transaction({
        "kind": "expense", "amount": 12345.67, "account_id": account_id,
        "category_id": int(expense["id"]), "tx_date": today,
        "description": "Prueba visual",
    })
    db.add_transaction({
        "kind": "income", "amount": 25000, "account_id": account_id,
        "category_id": int(income["id"]), "tx_date": today,
        "description": "Ingreso de prueba",
    })
    card = db.add_account("Tarjeta de prueba", "Tarjeta", 0, "#7A78E8", False,
                          credit_limit=200000, closing_day=20, due_day=10)
    db.add_transaction({
        "kind": "expense", "amount": 36000, "account_id": card,
        "category_id": int(expense["id"]), "tx_date": today,
        "description": "Compra 3 cuotas", "installments": 3,
    })


def main() -> int:
    errors: list[str] = []

    def hook(exc_type, exc, tb):
        formatted = "".join(traceback.format_exception(exc_type, exc, tb))
        errors.append(formatted)
        # El smoke test se ejecuta desde una consola visible en Windows. Si el
        # error no se imprime, el usuario sólo ve un mensaje genérico y no hay
        # información suficiente para diagnosticarlo.
        print(formatted, file=sys.stderr, flush=True)

    sys.excepthook = hook
    app = QApplication.instance() or QApplication([])
    normalize_application_font(app)

    with tempfile.TemporaryDirectory(prefix="appgastos_smoke_") as td:
        db = Database(Path(td) / "smoke.db")
        db.initialize()
        # Las instalaciones nuevas deben arrancar limpias: los datos históricos
        # usados durante el desarrollo no forman parte del producto distribuible.
        assert db.work_available_weeks() == []

        # Creamos datos genéricos sólo dentro de la base temporal del smoke test.
        trip_id = db.add_work_trip({
            "client": "Cliente prueba",
            "origin": "Origen",
            "destinations": ["Destino 1", "Destino 2", "Destino 3"],
            "trip_date": "2026-09-07",
            "bulky": False,
            "rain": False,
            "flex": True,
            "own_client": True,
            "details": "",
            "charged": 12000,
        })
        second_trip_id = db.add_work_trip({
            "client": "Segundo cliente",
            "origin": "Origen 2",
            "destinations": ["Destino único"],
            "trip_date": "2026-09-09",
            "bulky": True,
            "rain": False,
            "flex": False,
            "own_client": False,
            "details": "Prueba responsive",
            "charged": None,
        })
        db.add_work_extra({
            "app_name": "App demo",
            "work_date": "2026-09-08",
            "hours": 2.5,
            "orders": 4,
            "amount": 15000,
            "details": "",
        })
        db.set_work_day_mileage("2026-09-07", 1000.0, 1082.5)

        trip_summary = db.work_week_summary("2026-09-07")
        assert trip_summary["entries"] == 2, trip_summary
        assert trip_summary["trips"] == 2, trip_summary
        assert trip_summary["stops"] == 4, trip_summary
        assert trip_summary["flex"] == 3, trip_summary
        assert trip_summary["bulky"] == 1, trip_summary
        assert trip_summary["own_client"] == 1, trip_summary
        assert db.work_extra_week_summary("2026-09-07")["entries"] == 1

        # Repetir initialize no debe duplicar datos ni configuraciones.
        db.initialize()
        assert len(db.work_trips_for_week("2026-09-07")) == 2
        assert db.work_extra_week_summary("2026-09-07")["entries"] == 1

        mileage = db.work_week_mileage_summary("2026-09-07")
        assert mileage["real_km"] == 82.5, mileage
        assert mileage["completed_days"] == 1, mileage
        month = db.work_month_summary(2026, 9)
        assert month["trips"] == 2, month
        assert month["stops"] == 4, month
        assert month["flex"] == 3, month
        assert month["real_km"] == 82.5, month

        # Configuración editable: campos y tarifas deben poder coexistir con los
        # datos operativos sin depender del nombre elegido por el desarrollador.
        custom_field_id = db.save_work_field_definition({
            "label": "Contacto",
            "field_type": "text",
            "active": True,
            "show_in_summary": False,
        })
        rate_scheme_id = db.save_work_rate_scheme({
            "name": "Por distancia",
            "mode": "unit",
            "unit_label": "km",
            "unit_rate": 1050,
            "active": True,
            "options": [],
        })
        db.update_work_trip(trip_id, {
            "client": "Cliente prueba",
            "origin": "Origen",
            "destinations": ["Destino 1", "Destino 2", "Destino 3"],
            "trip_date": "2026-09-07",
            "flex": True,
            "own_client": True,
            "custom_fields": {custom_field_id: "demo@example.com"},
            "rate_scheme_id": rate_scheme_id,
            "rate_quantity": 20,
            "charged": 12000,
        })
        assert db.work_trip(trip_id)["custom_fields"][custom_field_id] == "demo@example.com"
        assert db.work_trip(trip_id)["calculated_price"] == 21000.0

        # Categorías multinivel y campos extendidos de v0.39.4 deben existir
        # antes de construir los diálogos para cubrir esos widgets en Windows.
        moto_id = db.add_category("Moto demo", "expense", None, "#7A78E8", "moto")
        glh_id = db.add_category("GLH demo", "expense", moto_id, "#7A78E8", "moto", "#E45567")
        db.add_category("Seguro demo", "expense", glh_id, "#E45567", "insurance")
        db.save_work_field_definition({
            "label": "Estado demo",
            "ui_type": "choice",
            "options": ["Pendiente", "Entregado"],
            "active": True,
            "show_in_summary": False,
        })
        db.save_work_field_definition({
            "label": "Email demo",
            "ui_type": "email",
            "active": True,
            "show_in_summary": False,
        })

        seed(db)

        # Verifica que todos los temas produzcan un stylesheet válido.
        themes = (
            "dark_mint", "dark_ocean", "dark_violet", "dark_sunset",
            "light_mint", "light_ocean", "light_violet", "light_sunset",
        )
        for theme in themes:
            app.setPalette(build_palette(theme))
            app.setStyleSheet(build_stylesheet(theme))
            app.processEvents()

        app.setPalette(build_palette("dark_mint"))
        app.setStyleSheet(build_stylesheet("dark_mint"))
        window = MainWindow(db)
        # Construcción explícita de componentes que históricamente generaron
        # crashes durante el arranque, para que el smoke test falle antes de abrir.
        flex_summary = db.flex_week_summary(date.today().isoformat())
        if flex_summary.get("zones"):
            probe = FlexZoneCard(dict(flex_summary["zones"][0]), db.currency_symbol(), db.balances_hidden())
            probe.deleteLater()
        # Herramientas se valida por TOPOLOGÍA de layout, no por coordenadas
        # provisionales. Qt puede dejar dos hijos de una página aún no activa en
        # (0, 0, sizeHint) aunque el QGridLayout sea correcto; usar esa geometría
        # como condición de arranque generaba falsos positivos en Windows.
        # Primero navegamos realmente a Herramientas y luego comprobamos que cada
        # acceso ocupa una celda distinta del grid.
        window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        window.resize(1480, 900)
        window.show()
        window.select_page(window.page_index["tools"])
        window.tools.show_home()
        window.tools._arrange_home_tiles(force=True)
        window.tools.home_grid.activate()
        app.processEvents()
        app.processEvents()

        assert window.stack.currentWidget() is window.tools
        assert window.tools.stack.currentWidget() is window.tools.home

        def grid_position(widget):
            index = window.tools.home_grid.indexOf(widget)
            assert index >= 0, f"Widget fuera del grid: {widget!r}"
            return window.tools.home_grid.getItemPosition(index)

        flex_pos = grid_position(window.tools.flex_tile)
        viajes_pos = grid_position(window.tools.viajes_tile)
        assert flex_pos != viajes_pos, (flex_pos, viajes_pos)
        assert window.tools.flex_tile.maximumHeight() <= 118
        assert window.tools.viajes_tile.maximumHeight() <= 118

        window.tools.open_flex()
        window.tools.flex.refresh()
        window.tools.open_viajes()
        window.tools.viajes.current_week = date(2026, 9, 7)
        window.tools.viajes.refresh()
        assert len(db.work_trips_for_week("2026-09-07")) == 2
        assert window.tools.viajes.trips_tree.day_count() == 7
        assert window.tools.viajes.extras_view.day_count() == 7
        assert all(name != "Presupuestos" for name, _icon, _page in window.pages)
        window.tools.viajes.set_trip_filter("flex")
        assert len(db.work_trips_for_week("2026-09-07", flag="flex")) == 1
        window.tools.viajes.set_trip_filter(None)
        app.processEvents()
        # La ventana está marcada WA_DontShowOnScreen: Qt resuelve geometrías,
        # fuentes y métricas con el backend nativo sin hacer visible el smoke test.
        app.processEvents()

        # Recorre todas las pantallas y fuerza dos formatos: escritorio y
        # monitor vertical/ventana angosta. Esto captura referencias de layout
        # inexistentes como los crashes responsive de versiones anteriores.
        for width, height in ((1480, 900), (768, 1280), (1024, 720)):
            window.resize(width, height)
            app.processEvents()
            for i, (_name, _icon, page) in enumerate(window.pages):
                window.select_page(i)
                if hasattr(page, "refresh"):
                    page.refresh()
                app.processEvents()

        # Modo privacidad: debe poder activarse/desactivarse sin romper
        # el stack ni los refresh de las pantallas.
        window.privacy_switch.setChecked(True)
        app.processEvents()
        window.select_page(0); app.processEvents()
        window.privacy_switch.setChecked(False)
        app.processEvents()

        # Flujos usados a diario: alta de movimiento y edición de categoría.
        tx = TransactionDialog(db, parent=window)
        app.processEvents(); tx.reject(); app.processEvents()
        category = db.categories("expense")[0]
        cat = CategoryDialog(db, category=category, parent=window)
        app.processEvents(); cat.reject(); app.processEvents()
        picker = CategoryPickerDialog(db, "expense", parent=window)
        app.processEvents(); picker.reject(); app.processEvents()
        breakdown = CategoryBreakdownDialog(
            db, "expense", moto_id, date(2026, 9, 1), date(2026, 9, 30), "month",
            lambda value: f"$ {float(value):,.0f}", window,
        )
        app.processEvents(); breakdown.reject(); app.processEvents()

        # Formularios del módulo de trabajo: deben construir sin depender de
        # datos de la base real ni del estado visual de la página.
        trip_dialog = TripDialog(db, default_date=date(2026, 9, 9), parent=window)
        app.processEvents(); trip_dialog.reject(); app.processEvents()
        extra_dialog = ExtraDialog(db, default_date=date(2026, 9, 9), parent=window)
        app.processEvents(); extra_dialog.reject(); app.processEvents()
        mileage_dialog = MileageWeekDialog(db, date(2026, 9, 7), parent=window)
        app.processEvents(); mileage_dialog.reject(); app.processEvents()
        calendar_dialog = CalendarDialog(QDate(2026, 9, 10), parent=window)
        app.processEvents(); calendar_dialog.reject(); app.processEvents()
        month_dialog = WorkMonthSummaryDialog(db, date(2026, 9, 10), parent=window)
        app.processEvents(); month_dialog.reject(); app.processEvents()
        customization_dialog = WorkCustomizationDialog(db, parent=window)
        app.processEvents(); customization_dialog.reject(); app.processEvents()
        zones_dialog = FlexRatesDialog(db, parent=window)
        app.processEvents(); zones_dialog.reject(); app.processEvents()

        window.close(); app.processEvents()

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("APP_GASTOS_SMOKE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
