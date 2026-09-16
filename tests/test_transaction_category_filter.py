import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication
from app.pages.transactions import TransactionsPage


class TransactionCategoryFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_kind_changes_remove_incompatible_selection_and_preserve_valid_one(self):
        db = Mock()
        db.accounts.return_value = []
        choices = {'expense': [{'label':'Casa', 'id':1}, {'label':'Casa / Alquiler', 'id':2}],
                   'income': [{'label':'Sueldo', 'id':3}]}
        db.category_choices.side_effect = lambda kind, tree: choices[kind]
        with patch.object(TransactionsPage, 'refresh') as refresh:
            page = TransactionsPage(db)
            try:
                ids = lambda: [page.category.itemData(i) for i in range(page.category.count())]
                self.assertEqual(ids(), [None,1,2,3])
                page.category.setCurrentIndex(page.category.findData(2))
                page.kind.setCurrentIndex(page.kind.findData('income'))
                self.assertEqual(ids(), [None,3])
                self.assertIsNone(page._filters()['category_id'])
                page.category.setCurrentIndex(1)
                page.kind.setCurrentIndex(page.kind.findData('all'))
                self.assertEqual(page._filters()['category_id'],3)
                page.kind.setCurrentIndex(page.kind.findData('expense'))
                self.assertEqual(ids(), [None,1,2])
                self.assertIsNone(page._filters()['category_id'])
                page.kind.setCurrentIndex(page.kind.findData('transfer'))
                self.assertEqual(ids(), [None])
                self.assertFalse(page.category.isEnabled())
                page.kind.setCurrentIndex(page.kind.findData('income'))
                page._load_filters()
                self.assertTrue(page.category.isEnabled())
                self.assertEqual(ids(), [None,3])
                refresh.assert_called()
            finally:
                page.deleteLater(); self.app.processEvents()


if __name__ == '__main__': unittest.main()
