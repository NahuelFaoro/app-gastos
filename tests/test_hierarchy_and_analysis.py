from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.db import Database


class CategoryHierarchyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tempdir.name) / "hierarchy.db")
        self.db.initialize()
        self.account_id = int(self.db.accounts()[0]["id"])

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_arbitrary_depth_and_full_path(self) -> None:
        root = self.db.add_category("Moto", "expense", None, "#7C3AED", "moto")
        glh = self.db.add_category("GLH", "expense", root, "#7C3AED", "moto", "#EF4444")
        insurance = self.db.add_category("Seguro", "expense", glh, "#EF4444", "insurance")
        category = self.db.category(insurance)
        self.assertEqual(category["path"], "Moto / GLH / Seguro")
        self.assertEqual(category["depth"], 2)
        self.assertEqual(self.db.category(glh)["secondary_color"], "#EF4444")

    def test_move_category_under_another_subcategory_without_losing_transaction(self) -> None:
        root = self.db.add_category("Moto", "expense", None, "#7C3AED", "moto")
        glh = self.db.add_category("GLH", "expense", root, "#EF4444", "moto")
        other = self.db.add_category("Otros", "expense", root, "#64748B", "other")
        leaf = self.db.add_category("Seguro", "expense", other, "#EF4444", "insurance")
        tx_id = self.db.add_transaction({
            "kind": "expense",
            "amount": 10000,
            "account_id": self.account_id,
            "category_id": leaf,
            "tx_date": "2026-09-11",
            "description": "Póliza",
            "note": "",
            "tags": "",
        })
        cat = self.db.category(leaf)
        self.db.update_category(leaf, cat["name"], cat["kind"], glh, cat["color"], cat["icon"], cat.get("secondary_color"))
        self.assertEqual(self.db.category(leaf)["path"], "Moto / GLH / Seguro")
        self.assertEqual(int(self.db.transaction(tx_id)["category_id"]), leaf)

    def test_move_category_helper_preserves_subtree_and_transaction_ids(self) -> None:
        root = self.db.add_category("Moto", "expense", None, "#7C3AED", "moto")
        glh = self.db.add_category("GLH", "expense", root, "#EF4444", "moto")
        target = self.db.add_category("Trabajo", "expense", None, "#22C55E", "work")
        leaf = self.db.add_category("Seguro", "expense", glh, "#EF4444", "insurance")
        tx_id = self.db.add_transaction({
            "kind": "expense", "amount": 7000, "account_id": self.account_id,
            "category_id": leaf, "tx_date": "2026-09-11", "description": "Póliza",
            "note": "", "tags": "",
        })
        self.db.move_category(glh, target)
        self.assertEqual(self.db.category(glh)["path"], "Trabajo / GLH")
        self.assertEqual(self.db.category(leaf)["path"], "Trabajo / GLH / Seguro")
        self.assertEqual(int(self.db.transaction(tx_id)["category_id"]), leaf)

    def test_move_category_never_changes_category_row_count(self) -> None:
        root = self.db.add_category("Moto", "expense", None, "#7C3AED", "moto")
        child = self.db.add_category("GLH", "expense", None, "#EF4444", "moto")
        before_ids = {int(row["id"]) for row in self.db.categories("expense")}
        self.db.move_category(child, root)
        after_ids = {int(row["id"]) for row in self.db.categories("expense")}
        self.assertEqual(before_ids, after_ids)
        self.assertEqual(self.db.category(child)["parent_id"], root)

    def test_move_repairs_empty_same_name_duplicate_in_destination(self) -> None:
        target = self.db.add_category("Compras", "expense", None, "#7C3AED", "cart")
        stale = self.db.add_category("Makro", "expense", target, "#7C3AED", "cart")
        source = self.db.add_category("Makro", "expense", None, "#7C3AED", "cart")
        tx_id = self.db.add_transaction({
            "kind": "expense", "amount": 4200, "account_id": self.account_id,
            "category_id": source, "tx_date": "2026-09-11", "description": "Compra",
            "note": "", "tags": "",
        })
        self.db.move_category(source, target)
        self.assertIsNone(self.db.category(stale))
        self.assertEqual(int(self.db.category(source)["parent_id"]), target)
        self.assertEqual(int(self.db.transaction(tx_id)["category_id"]), source)
        makros = [
            row for row in self.db.category_children(target, "expense")
            if str(row.get("name") or "").casefold() == "makro"
        ]
        self.assertEqual([int(row["id"]) for row in makros], [source])

    def test_move_refuses_to_delete_same_name_duplicate_that_has_data(self) -> None:
        target = self.db.add_category("Compras", "expense", None, "#7C3AED", "cart")
        occupied = self.db.add_category("Makro", "expense", target, "#7C3AED", "cart")
        source = self.db.add_category("Makro", "expense", None, "#7C3AED", "cart")
        self.db.add_transaction({
            "kind": "expense", "amount": 1000, "account_id": self.account_id,
            "category_id": occupied, "tx_date": "2026-09-11", "description": "Existente",
            "note": "", "tags": "",
        })
        with self.assertRaises(ValueError):
            self.db.move_category(source, target)
        self.assertIsNone(self.db.category(source)["parent_id"])
        self.assertEqual(int(self.db.category(occupied)["parent_id"]), target)

    def test_duplicate_category_copies_visuals_but_not_children_or_movements(self) -> None:
        root = self.db.add_category("Moto", "expense", None, "#7C3AED", "moto")
        glh = self.db.add_category("GLH", "expense", root, "#7C3AED", "moto", "#EF4444")
        leaf = self.db.add_category("Seguro", "expense", glh, "#EF4444", "insurance")
        self.db.add_transaction({
            "kind": "expense", "amount": 9000, "account_id": self.account_id,
            "category_id": glh, "tx_date": "2026-09-11", "description": "Dato original",
            "note": "", "tags": "",
        })
        duplicate_id = self.db.duplicate_category(glh)
        duplicate = self.db.category(duplicate_id)
        self.assertNotEqual(duplicate_id, glh)
        self.assertEqual(duplicate["parent_id"], root)
        self.assertEqual(duplicate["color"], "#7C3AED")
        self.assertEqual(duplicate["secondary_color"], "#EF4444")
        self.assertEqual(self.db.category_children(duplicate_id, "expense"), [])
        self.assertEqual(self.db.transactions(category_id=duplicate_id), [])
        self.assertEqual(self.db.category(leaf)["path"], "Moto / GLH / Seguro")

    def test_cycle_is_rejected(self) -> None:
        root = self.db.add_category("Moto", "expense", None, "#7C3AED", "moto")
        glh = self.db.add_category("GLH", "expense", root, "#EF4444", "moto")
        leaf = self.db.add_category("Seguro", "expense", glh, "#EF4444", "insurance")
        root_data = self.db.category(root)
        with self.assertRaises(ValueError):
            self.db.update_category(root, root_data["name"], root_data["kind"], leaf, root_data["color"], root_data["icon"])

    def test_root_analysis_aggregates_deep_descendants(self) -> None:
        root = self.db.add_category("Moto", "expense", None, "#7C3AED", "moto")
        glh = self.db.add_category("GLH", "expense", root, "#EF4444", "moto")
        insurance = self.db.add_category("Seguro", "expense", glh, "#EF4444", "insurance")
        fuel = self.db.add_category("Nafta", "expense", glh, "#F59E0B", "fuel")
        for cid, amount in ((insurance, 80000), (fuel, 20000)):
            self.db.add_transaction({
                "kind": "expense",
                "amount": amount,
                "account_id": self.account_id,
                "category_id": cid,
                "tx_date": "2026-09-11",
                "description": "",
                "note": "",
                "tags": "",
            })
        rows = self.db.category_totals_period("expense", "2026-09-01", "2026-09-30", include_history=False)
        moto = next(row for row in rows if int(row.get("category_id") or 0) == root)
        self.assertEqual(moto["total"], 100000)
        children = self.db.category_direct_children_totals_period("expense", root, "2026-09-01", "2026-09-30")
        glh_row = next(row for row in children if int(row["category_id"]) == glh)
        self.assertEqual(glh_row["total"], 100000)


    def test_deep_category_path_is_used_by_choices_transactions_and_recurring(self) -> None:
        root = self.db.add_category("Moto", "expense", None, "#7C3AED", "moto")
        glh = self.db.add_category("GLH", "expense", root, "#7C3AED", "moto", "#EF4444")
        leaf = self.db.add_category("Seguro", "expense", glh, "#EF4444", "insurance")
        choices = {int(row["id"]): row for row in self.db.category_choices("expense", include_parents=False)}
        self.assertEqual(choices[leaf]["label"], "Moto / GLH / Seguro")

        self.db.add_transaction({
            "kind": "expense", "amount": 1234, "account_id": self.account_id,
            "category_id": leaf, "tx_date": "2026-09-11", "description": "Póliza",
            "note": "", "tags": "",
        })
        tx = self.db.transactions(category_id=root)[0]
        self.assertEqual(tx["category_display"], "Moto / GLH / Seguro")

        self.db.add_recurring({
            "kind": "expense", "amount": 5000, "account_id": self.account_id,
            "category_id": leaf, "description": "Seguro mensual", "note": "", "tags": "",
            "tx_date": "2026-09-11", "frequency": "monthly", "interval_value": 1, "next_date": "2026-10-11",
        })
        recurring = self.db.recurring()[0]
        self.assertEqual(recurring["category_display"], "Moto / GLH / Seguro")
        self.assertEqual(recurring["category_secondary_color"], None)

    def test_analysis_movements_can_sort_by_amount(self) -> None:
        root = self.db.add_category("Moto", "expense", None, "#7C3AED", "moto")
        leaf = self.db.add_category("Otros", "expense", root, "#64748B", "other")
        for amount, day in ((2000, "2026-09-11"), (50000, "2026-09-09"), (10000, "2026-09-10")):
            self.db.add_transaction({
                "kind": "expense",
                "amount": amount,
                "account_id": self.account_id,
                "category_id": leaf,
                "tx_date": day,
                "description": str(amount),
                "note": "",
                "tags": "",
            })
        desc = self.db.category_transactions_period("expense", leaf, "2026-09-01", "2026-09-30", "amount_desc")
        asc = self.db.category_transactions_period("expense", leaf, "2026-09-01", "2026-09-30", "amount_asc")
        self.assertEqual([row["amount"] for row in desc], [50000, 10000, 2000])
        self.assertEqual([row["amount"] for row in asc], [2000, 10000, 50000])


class WorkFieldTypeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tempdir.name) / "fields.db")
        self.db.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()


    def test_all_extended_field_types_roundtrip(self) -> None:
        definitions = {
            "Nota larga": ("long_text", "Una observación extensa"),
            "Teléfono": ("phone", "+54 11 5555-0000"),
            "Cantidad": ("number", 3.5),
            "Precio": ("money", 12500.75),
        }
        values: dict[int, object] = {}
        for label, (ui_type, value) in definitions.items():
            field_id = self.db.save_work_field_definition({
                "label": label,
                "ui_type": ui_type,
                "active": True,
                "show_in_summary": False,
            })
            values[field_id] = value
        trip_id = self.db.add_work_trip({
            "client": "Cliente", "origin": "A", "destinations": ["B"],
            "trip_date": "2026-09-11", "custom_fields": values,
        })
        stored = self.db.work_trip(trip_id)["custom_fields"]
        for field_id, expected in values.items():
            if isinstance(expected, float):
                self.assertAlmostEqual(float(stored[field_id]), expected)
            else:
                self.assertEqual(stored[field_id], expected)

    def test_extended_text_types_and_choice_roundtrip(self) -> None:
        email_id = self.db.save_work_field_definition({
            "label": "Email",
            "ui_type": "email",
            "active": True,
            "show_in_summary": False,
        })
        choice_id = self.db.save_work_field_definition({
            "label": "Estado",
            "ui_type": "choice",
            "options": ["Pendiente", "Entregado"],
            "active": True,
            "show_in_summary": False,
        })
        definitions = {int(row["id"]): row for row in self.db.work_field_definitions()}
        self.assertEqual(definitions[email_id]["field_type"], "text")
        self.assertEqual(definitions[email_id]["ui_type"], "email")
        self.assertEqual(definitions[choice_id]["options"], ["Pendiente", "Entregado"])

        trip_id = self.db.add_work_trip({
            "client": "Cliente",
            "origin": "A",
            "destinations": ["B"],
            "trip_date": "2026-09-11",
            "custom_fields": {email_id: "a@example.com", choice_id: "Entregado"},
        })
        values = self.db.work_trip(trip_id)["custom_fields"]
        self.assertEqual(values[email_id], "a@example.com")
        self.assertEqual(values[choice_id], "Entregado")


if __name__ == "__main__":
    unittest.main()
