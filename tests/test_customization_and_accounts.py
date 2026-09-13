from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.db import Database


class AccountSemanticsTests(unittest.TestCase):
    """Regresiones de patrimonio y tarjetas pagadas."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tempdir.name) / "accounts.db")
        self.db.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_paid_credit_card_never_becomes_positive_asset(self) -> None:
        cash = next(a for a in self.db.accounts() if a["name"] == "Efectivo")
        wallet = next(a for a in self.db.accounts() if a["name"] == "Mercado Pago")
        self.db.update_account(cash["id"], "Efectivo", "Efectivo", -500_000, cash["color"], True)
        self.db.update_account(wallet["id"], "Mercado Pago", "Billetera", -36_072.74, wallet["color"], True)
        self.db.add_account("Ahorros", "Ahorro", 1_285_338.45, "#8A2BE2", False)
        card_id = self.db.add_account("Tarjeta paga", "Tarjeta", 1_227_531.53, "#EF4444", False, 2_000_000, 1, 10)

        card = next(a for a in self.db.accounts_with_balances() if int(a["id"]) == card_id)
        self.assertEqual(card["balance"], 0.0)
        self.assertGreater(card["raw_balance"], 0.0)
        self.assertAlmostEqual(self.db.net_worth(), 1_285_338.45, places=2)


class WorkCustomizationTests(unittest.TestCase):
    """Campos dinámicos, tarifas y orden configurable sin tocar la UI."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tempdir.name) / "custom.db")
        self.db.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_custom_text_field_roundtrip_and_search(self) -> None:
        field_id = self.db.save_work_field_definition({
            "label": "Contacto",
            "field_type": "text",
            "active": True,
            "show_in_summary": False,
        })
        trip_id = self.db.add_work_trip({
            "client": "Cliente demo",
            "origin": "Origen",
            "destinations": ["Destino"],
            "trip_date": "2026-09-07",
            "custom_fields": {field_id: "persona@example.com"},
        })
        trip = self.db.work_trip(trip_id)
        self.assertEqual(trip["custom_fields"][field_id], "persona@example.com")
        rows = self.db.work_trips_for_week("2026-09-07", search="persona@example.com")
        self.assertEqual([row["id"] for row in rows], [trip_id])


    def test_used_custom_field_is_soft_deleted_to_preserve_history(self) -> None:
        field_id = self.db.save_work_field_definition({
            "label": "Mail",
            "field_type": "text",
            "active": True,
            "show_in_summary": False,
        })
        trip_id = self.db.add_work_trip({
            "client": "Cliente",
            "origin": "A",
            "destinations": ["B"],
            "trip_date": "2026-09-07",
            "custom_fields": {field_id: "persona@example.com"},
        })
        self.db.delete_work_field_definition(field_id)
        definition = next(d for d in self.db.work_field_definitions() if int(d["id"]) == field_id)
        self.assertFalse(bool(definition["active"]))
        self.assertEqual(self.db.work_trip(trip_id)["custom_fields"][field_id], "persona@example.com")

    def test_builtin_field_can_be_renamed_hidden_and_reordered(self) -> None:
        definitions = self.db.work_field_definitions()
        flex = next(d for d in definitions if d.get("built_in_key") == "flex")
        flex_id = int(flex["id"])
        self.db.save_work_field_definition({
            "label": "Pedidos Flex",
            "field_type": "text",  # el repositorio debe mantener el tipo nativo check
            "active": False,
            "show_in_summary": False,
        }, flex_id)
        reordered = [flex_id] + [int(d["id"]) for d in definitions if int(d["id"]) != flex_id]
        self.db.reorder_work_fields(reordered)
        updated = self.db.work_field_definitions()
        self.assertEqual(int(updated[0]["id"]), flex_id)
        self.assertEqual(updated[0]["label"], "Pedidos Flex")
        self.assertEqual(updated[0]["field_type"], "check")
        self.assertFalse(bool(updated[0]["active"]))


    def test_partial_trip_update_preserves_hidden_configurable_values(self) -> None:
        field_id = self.db.save_work_field_definition({
            "label": "Referencia interna",
            "field_type": "text",
            "active": True,
            "show_in_summary": False,
        })
        trip_id = self.db.add_work_trip({
            "client": "Cliente",
            "origin": "A",
            "destinations": ["B"],
            "trip_date": "2026-09-07",
            "flex": True,
            "custom_fields": {field_id: "ABC-123"},
        })
        self.db.save_work_field_definition({
            "label": "Referencia interna",
            "field_type": "text",
            "active": False,
            "show_in_summary": False,
        }, field_id)
        flex = next(d for d in self.db.work_field_definitions() if d.get("built_in_key") == "flex")
        self.db.save_work_field_definition({
            "label": "Flex",
            "field_type": "check",
            "active": False,
            "show_in_summary": False,
        }, int(flex["id"]))

        # Simula un formulario que ya no contiene esos campos ocultos.
        self.db.update_work_trip(trip_id, {
            "client": "Cliente editado",
            "origin": "A",
            "destinations": ["B", "C"],
            "trip_date": "2026-09-07",
            "details": "",
            "charged": None,
        })
        trip = self.db.work_trip(trip_id)
        self.assertTrue(bool(trip["flex"]))
        self.assertEqual(trip["custom_fields"][field_id], "ABC-123")
        self.assertEqual(trip["stop_count"], 2)

    def test_unit_rate_calculates_and_is_frozen_on_trip(self) -> None:
        scheme_id = self.db.save_work_rate_scheme({
            "name": "Por kilometraje",
            "mode": "unit",
            "unit_label": "km",
            "unit_rate": 1050,
            "active": True,
            "options": [],
        })
        trip_id = self.db.add_work_trip({
            "client": "Cliente",
            "origin": "A",
            "destinations": ["B"],
            "trip_date": "2026-09-07",
            "rate_scheme_id": scheme_id,
            "rate_quantity": 20,
        })
        trip = self.db.work_trip(trip_id)
        self.assertAlmostEqual(float(trip["calculated_price"]), 21_000.0)


    def test_existing_rate_snapshot_survives_unrelated_trip_edit(self) -> None:
        scheme_id = self.db.save_work_rate_scheme({
            "name": "Por unidad",
            "mode": "unit",
            "unit_label": "km",
            "unit_rate": 1000,
            "active": True,
            "options": [],
        })
        trip_id = self.db.add_work_trip({
            "client": "Cliente",
            "origin": "A",
            "destinations": ["B"],
            "trip_date": "2026-09-07",
            "rate_scheme_id": scheme_id,
            "rate_quantity": 10,
        })
        self.assertEqual(float(self.db.work_trip(trip_id)["calculated_price"]), 10_000.0)

        # La tarifa global cambia después del viaje.
        self.db.save_work_rate_scheme({
            "name": "Por unidad",
            "mode": "unit",
            "unit_label": "km",
            "unit_rate": 2000,
            "active": True,
            "options": [],
        }, scheme_id)
        self.db.update_work_trip(trip_id, {
            "client": "Cliente editado",
            "origin": "A",
            "destinations": ["B"],
            "trip_date": "2026-09-07",
            "rate_scheme_id": scheme_id,
            "rate_quantity": 10,
            "rate_option_id": None,
            "details": "Cambio de nota",
            "charged": None,
        })
        self.assertEqual(float(self.db.work_trip(trip_id)["calculated_price"]), 10_000.0)

    def test_option_rate_uses_selected_option(self) -> None:
        scheme_id = self.db.save_work_rate_scheme({
            "name": "Por zona",
            "mode": "option",
            "unit_label": "zona",
            "unit_rate": 0,
            "active": True,
            "options": [
                {"label": "Zona 1", "rate": 4500},
                {"label": "Zona 2", "rate": 6990},
            ],
        })
        scheme = next(s for s in self.db.work_rate_schemes() if int(s["id"]) == scheme_id)
        zone_2 = next(opt for opt in scheme["options"] if opt["label"] == "Zona 2")
        self.assertAlmostEqual(self.db.calculate_work_rate(scheme_id, None, zone_2["id"]), 6990.0)

    def test_flex_zones_can_be_reordered(self) -> None:
        zones = self.db.flex_zones(include_inactive=True)
        reversed_ids = [int(z["id"]) for z in reversed(zones)]
        self.db.reorder_flex_zones(reversed_ids)
        actual = [int(z["id"]) for z in self.db.flex_zones(include_inactive=True)]
        self.assertEqual(actual, reversed_ids)

    def test_flex_unused_zone_can_be_deleted_but_used_zone_is_protected(self) -> None:
        unused = self.db.add_flex_zone("Temporal", 1234, "2026-09-12")
        self.assertEqual(self.db.flex_zone_delivery_count(unused), 0)
        self.db.delete_flex_zone(unused)
        self.assertIsNone(self.db.flex_zone(unused))

        used = self.db.add_flex_zone("Con historial", 2500, "2026-09-12")
        self.db.add_flex_delivery(used, "2026-09-07", 1, "2026-09-12")
        self.assertEqual(self.db.flex_zone_delivery_count(used), 1)
        with self.assertRaises(ValueError):
            self.db.delete_flex_zone(used)
        self.assertIsNotNone(self.db.flex_zone(used))



if __name__ == "__main__":
    unittest.main()
