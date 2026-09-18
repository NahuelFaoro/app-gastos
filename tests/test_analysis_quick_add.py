import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from datetime import date
from unittest.mock import Mock, patch
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QDialog
from app.pages.statistics import CategoryBreakdownDialog


class AnalysisQuickAddTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_add_uses_current_drilled_category_and_period_then_refreshes(self):
        for kind in ('income','expense'):
            db=Mock(); db.category.return_value={'id':17,'name':'Subcategoría','color':'#123456'}
            with patch.object(CategoryBreakdownDialog,'_refresh') as refresh:
                view=CategoryBreakdownDialog(db,kind,1,date(2020,2,1),date(2020,2,29),'month',str)
                view.current_category_id=17
                changed=Mock();view.data_changed.connect(changed)
                dialog=Mock();dialog.exec.return_value=QDialog.DialogCode.Accepted
                dialog.data.return_value={'kind':kind,'category_id':17,'amount':100}
                with patch('app.pages.statistics.TransactionDialog',return_value=dialog):view._add_movement()
                dialog.set_kind.assert_called_once_with(kind)
                dialog.category.set_category.assert_called_once_with(db.category.return_value)
                dialog.date.setDate.assert_called_once_with(QDate(2020,2,29))
                db.add_transaction.assert_called_once_with(dialog.data.return_value)
                changed.assert_called_once();self.assertEqual(refresh.call_count,2)
                db.add_transaction.reset_mock();changed.reset_mock()
                dialog.exec.return_value=QDialog.DialogCode.Rejected
                with patch('app.pages.statistics.TransactionDialog',return_value=dialog):view._add_movement()
                db.add_transaction.assert_not_called();changed.assert_not_called()
                view.deleteLater();self.app.processEvents()


if __name__=='__main__':unittest.main()
