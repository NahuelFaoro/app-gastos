import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.amounts import decimal_amount
from app.db import Database


class AmountTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Database(Path(self.tmp.name) / "test.db")
        self.db.initialize()
        self.card = self.db.add_account("Tarjeta", "Tarjeta", 0, "#123456")
        category = self.db.categories("expense")[0]["id"]
        self.data = dict(kind="expense", amount=100, account_id=self.card,
                         category_id=category, tx_date="2026-01-01")

    def test_decimal_rounding_and_rejects_nonfinite_values(self):
        self.assertEqual(decimal_amount("2.675"), Decimal("2.68"))
        for value in ("NaN", "Infinity", "-Infinity", "1e999", "invalid"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.db.add_transaction({**self.data, "amount": value})
        self.assertEqual(self.db.transactions(), [])

    def test_create_and_update_round_to_cents_without_mutating_input(self):
        data = {**self.data, "amount": "2.675"}
        tx_id = self.db.add_transaction(data)
        self.assertEqual(data["amount"], "2.675")
        self.assertEqual(self.db.transaction(tx_id)["amount"], 2.68)
        self.db.update_transaction(tx_id, {**data, "amount": "1.005"})
        self.assertEqual(self.db.transaction(tx_id)["amount"], 1.01)
        with self.assertRaises(ValueError):
            self.db.update_transaction(tx_id, {**data, "amount": "NaN"})
        self.assertEqual(self.db.transaction(tx_id)["amount"], 1.01)

    def test_installments_sum_to_purchase_and_match_projection(self):
        tx_id = self.db.add_transaction({**self.data, "amount": "2.01", "installments": 2})
        plan_id = self.db.transaction(tx_id)["installment_plan_id"]
        projected = self.db.installment_monthly_commitments(2026, 1, 2)
        self.assertEqual([row["total"] for row in projected], [1.01, 1.0])
        self.assertEqual(self.db.process_due_installments(date(2026, 3, 1)), 1)
        rows = self.db.installment_transactions(plan_id)
        self.assertEqual(sum(Decimal(str(r["amount"])) for r in rows), Decimal("2.01"))
        self.assertEqual(self.db.process_due_installments(date(2026, 3, 1)), 0)

    def test_invalid_tiny_installment_plan_is_atomic(self):
        with self.assertRaises(ValueError):
            self.db.add_transaction({**self.data, "amount": "0.02", "installments": 4})
        self.assertEqual(self.db.installment_plans(), [])
        self.assertEqual(self.db.transactions(), [])

    def test_reopening_preserves_legacy_amounts_and_plan_base(self):
        tx_id = self.db.add_transaction({**self.data, "installments": 3})
        plan_id = self.db.transaction(tx_id)["installment_plan_id"]
        # Representa un valor histórico previo a la normalización de entradas.
        with self.db.connect() as con:
            con.execute("UPDATE transactions SET amount=1.2345 WHERE id=?", (tx_id,))
        reopened = Database(self.db.path)
        reopened.initialize()
        self.assertEqual(reopened.transaction(tx_id)["amount"], 1.2345)
        self.assertEqual(reopened.installment_plan(plan_id)["base_amount"], 33.33)
        self.assertEqual(reopened.process_due_installments(date(2026, 4, 1)), 2)
        self.assertEqual(reopened.installment_transactions(plan_id)[-1]["amount"], 33.34)
