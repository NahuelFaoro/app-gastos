import tempfile
import unittest
from pathlib import Path
from app.db import Database
from app.work_income import income_draft
from app.cloud_bridge import export_cloud, apply_cloud


class AnalysisAndWorkIncomeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Database(Path(self.tmp.name)/'test.db');self.db.initialize()
        self.account=self.db.accounts()[0]['id']
        self.category=self.db.add_category('Test aplicaciones','income',None,'#123456')

    def tearDown(self):self.tmp.cleanup()

    def tx(self,category,amount):
        return dict(kind='income',category_id=category,account_id=self.account,amount=amount,tx_date='2026-09-15')

    def test_root_matches_children_with_different_secondary_colors(self):
        a=self.db.add_category('Test A','income',self.category,'#123456',secondary_color='#ff0000')
        b=self.db.add_category('Test B','income',self.category,'#123456')
        self.db.add_transaction(self.tx(a,64452.33));self.db.add_transaction(self.tx(b,49039.04))
        start,end='2026-09-01','2026-09-30'
        rows=self.db.category_totals_period('income',start,end)
        root=next(r for r in rows if r['category_id']==self.category)
        self.assertAlmostEqual(root['total'],113491.37)
        self.assertEqual(root['tx_count'],2)
        self.assertAlmostEqual(root['total'],self.db.category_subtree_total_period('income',self.category,start,end))
        self.assertAlmostEqual(root['total'],sum(r['total'] for r in self.db.category_direct_children_totals_period('income',self.category,start,end)))
        self.assertAlmostEqual(sum(r['total'] for r in rows),self.db.period_summary(start,end)['income'])

    def test_income_draft_and_duplicate_guard_for_both_tools(self):
        trip=self.db.add_work_trip(dict(client='Test',trip_date='2026-09-15',destinations=['Destino'],charged=12000))
        extra=self.db.add_work_extra(dict(app_name='Test app',work_date='2026-09-16',hours=2,amount=19378))
        for kind,record_id,amount in [('trip',trip,12000),('extra',extra,19378)]:
            draft=income_draft(self.db,kind,record_id)
            self.assertEqual(draft['amount'],amount)
            self.assertEqual(draft['kind'],'income')
            data={**draft,'account_id':self.account,'category_id':self.category}
            tx_id=self.db.add_transaction(data,source=draft['source'],external_id=draft['external_id'])
            with self.assertRaisesRegex(ValueError,'ya tiene un ingreso'):income_draft(self.db,kind,record_id)
            with self.assertRaisesRegex(ValueError,'ya tiene un ingreso'):
                self.db.add_transaction(data,source=draft['source'],external_id=draft['external_id'])
            self.db.delete_transaction(tx_id)
            self.assertEqual(income_draft(self.db,kind,record_id)['external_id'],draft['external_id'])

    def test_link_survives_transfer_to_another_desktop(self):
        extra=self.db.add_work_extra(dict(app_name='Test app',work_date='2026-09-16',hours=2,amount=19378))
        draft=income_draft(self.db,'extra',extra)
        self.db.add_transaction({**draft,'account_id':self.account,'category_id':self.category},source=draft['source'],external_id=draft['external_id'])
        document=export_cloud(self.db)
        other=Database(Path(self.tmp.name)/'other.db');other.initialize()
        apply_cloud(other,document,export_cloud(other),document,1)
        with other.connect() as con:other_id=con.execute('SELECT id FROM work_extras').fetchone()[0]
        with self.assertRaisesRegex(ValueError,'ya tiene un ingreso'):income_draft(other,'extra',other_id)

    def test_no_income_for_empty_collected_amount(self):
        trip=self.db.add_work_trip(dict(client='Test',trip_date='2026-09-15',destinations=['Destino']))
        with self.assertRaisesRegex(ValueError,'mayor a cero'):income_draft(self.db,'trip',trip)


if __name__=='__main__':unittest.main()
