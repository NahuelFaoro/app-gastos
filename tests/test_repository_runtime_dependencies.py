from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.db import Database


class RepositoryRuntimeDependencyTests(unittest.TestCase):
    """Ejercita rutas que dependen de helpers importados por cada repositorio.

    Esta suite existe específicamente para evitar regresiones de refactors donde
    un método se mueve desde db.py pero se olvida importar uno de sus helpers.
    ``compileall`` no detecta ese tipo de NameError; ejecutar las rutas sí.
    """

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tempdir.name) / "runtime_dependencies.db")
        self.db.initialize()
        self.expense = self.db.category_choices("expense", include_parents=False)[0]
        self.account = self.db.accounts()[0]

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_transaction_installments_and_calendar_helpers_are_resolved(self) -> None:
        card_id = self.db.add_account(
            "Tarjeta runtime", "Tarjeta", 0, "#7A78E8", False,
            credit_limit=100_000, closing_day=20, due_day=10,
        )
        tx_id = self.db.add_transaction({
            "kind": "expense",
            "amount": 30_000,
            "account_id": card_id,
            "category_id": int(self.expense["id"]),
            "tx_date": "2026-09-12",
            "description": "Compra en 3 cuotas",
            "installments": 3,
        })
        self.assertGreater(tx_id, 0)
        plans = self.db.installment_plans(card_id, active_only=True)
        self.assertEqual(len(plans), 1)
        commitments = self.db.installment_monthly_commitments(2026, 9, 4)
        self.assertGreaterEqual(len(commitments), 1)
        daily = self.db.daily_totals(2026, 9)
        self.assertIn("2026-09-12", daily)

    def test_planning_analytics_import_queue_and_history_helpers_are_resolved(self) -> None:
        self.db.add_transaction({
            "kind": "expense",
            "amount": 1_500,
            "account_id": int(self.account["id"]),
            "category_id": int(self.expense["id"]),
            "tx_date": "2026-09-10",
            "description": "Gasto runtime",
        })
        budget_id = self.db.add_budget({
            "name": "Presupuesto runtime",
            "amount": 10_000,
            "category_id": int(self.expense["id"]),
            "account_id": None,
            "start_date": "2026-01-01",
        })
        self.assertGreater(budget_id, 0)
        status = self.db.budget_status(2026, 9)
        self.assertTrue(any(int(row["id"]) == budget_id for row in status))

        staged = self.db.stage_imported_movements([
            {
                "external_id": "runtime-1",
                "kind": "expense",
                "amount": 999,
                "tx_date": "2026-09-11",
                "description": "Compra importada",
                "raw": {"source": "runtime"},
            }
        ], "runtime", int(self.account["id"]))
        self.assertEqual(staged["inserted"], 1)
        duplicated = self.db.stage_imported_movements([
            {
                "external_id": "runtime-1",
                "kind": "expense",
                "amount": 999,
                "tx_date": "2026-09-11",
                "description": "Compra importada",
                "raw": {"source": "runtime"},
            }
        ], "runtime", int(self.account["id"]))
        self.assertEqual(duplicated["duplicates"], 1)
        self.assertEqual(len(self.db.imported_movements("pending", "runtime")), 1)

        payload = {
            "file_name": "runtime.xlsx",
            "file_hash": "runtime-history-hash",
            "category_paths": [
                {"kind": "expense", "category_name": "Histórico runtime", "subcategory_name": "Detalle"}
            ],
            "records": [
                {
                    "kind": "expense", "year": 2020, "month": 1,
                    "category_name": "Histórico runtime", "subcategory_name": "Detalle", "amount": 2500,
                }
            ],
        }
        imported = self.db.import_monthly_history(
            payload,
            skip_transaction_months=False,
            skip_existing_history_months=False,
            closed_months_only=True,
        )
        self.assertEqual(imported["rows"], 1)
        analysis = self.db.category_totals_period("expense", "2020-01-01", "2020-01-31", include_history=True)
        self.assertTrue(any(float(row.get("total") or 0) == 2500 for row in analysis))
        self.assertIsInstance(self.db.monthly_summary(2026, 9), dict)

    def test_mobile_server_uses_shared_week_start_name(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "app" / "mobile_server.py").read_text(encoding="utf-8")
        self.assertNotIn("_week_start(date.today())", source)
        self.assertIn("week_start(date.today())", source)


if __name__ == "__main__":
    unittest.main()
