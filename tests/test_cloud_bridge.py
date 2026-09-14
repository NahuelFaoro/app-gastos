import copy
import tempfile
import unittest
from pathlib import Path
from app.db import Database
from app.cloud_bridge import export_cloud,apply_cloud,merge_copies

class CloudBridgeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.db=Database(Path(self.tmp.name)/'test.db');self.db.initialize()
 def tearDown(self):self.tmp.cleanup()
 def test_roundtrip_add_and_update_transactions(self):
  local=export_cloud(self.db);remote=copy.deepcopy(local);a=remote['accounts'][0]['id'];c=next(c['id'] for c in remote['categories'] if c['kind']=='expense')
  remote['transactions'].append(dict(id='new-mobile',kind='expense',amount=12345,account=a,to='',category=c,date='2026-01-01',description='Prueba',note='',tags=''))
  apply_cloud(self.db,remote,local,remote,1)
  result=export_cloud(self.db);t=next(t for t in result['transactions'] if t['id']=='new-mobile');self.assertEqual(t['amount'],12345)
  changed=copy.deepcopy(result);changed['transactions'][0]['amount']=99999;apply_cloud(self.db,changed,result,changed,2);self.assertEqual(export_cloud(self.db)['transactions'][0]['amount'],99999)
 def test_stale_snapshot_does_not_overwrite_new_local_record(self):
  local=export_cloud(self.db)
  with self.db.connect() as c:c.execute("UPDATE accounts SET opening_balance=700 WHERE id=(SELECT min(id) FROM accounts)")
  with self.assertRaisesRegex(ValueError,'Hubo cambios'):apply_cloud(self.db,local,local,local,1)
  self.assertNotEqual(export_cloud(self.db)['accounts'],local['accounts'])
 def test_bad_reference_rolls_back_account_changes(self):
  local=export_cloud(self.db);remote=copy.deepcopy(local);remote['accounts'][0]['initial']=10000
  remote['transactions']=[dict(id='bad',kind='expense',amount=100,account='missing',date='2026-01-01',category='')]
  with self.assertRaises(ValueError):apply_cloud(self.db,remote,local,remote,1)
  self.assertEqual(export_cloud(self.db),local)
 def test_independent_and_conflicting_edits(self):
  base=export_cloud(self.db);local=copy.deepcopy(base);remote=copy.deepcopy(base);local['accounts'][0]['initial']=100;remote['categories'][0]['name']='Cambio'
  merged,conflicts=merge_copies(base,local,remote);self.assertFalse(conflicts);self.assertEqual(merged['accounts'][0]['initial'],100)
  remote['accounts'][0]['initial']=200;self.assertTrue(merge_copies(base,local,remote)[1])
 def test_receive_independent_database_with_same_seed_names(self):
  other=Database(Path(self.tmp.name)/'other.db');other.initialize()
  local=export_cloud(self.db);remote=export_cloud(other)
  apply_cloud(self.db,remote,local,remote,1)
  result=export_cloud(self.db)
  self.assertEqual(result['accounts'],remote['accounts'])
  self.assertEqual(result['categories'],remote['categories'])
 def test_delivery_keeps_mobile_day(self):
  local=export_cloud(self.db);remote=copy.deepcopy(local)
  remote['deliveries'].append(dict(id='delivery-test',zone=remote['zones'][0]['id'],date='2026-09-17',quantity=1,amount=10000))
  apply_cloud(self.db,remote,local,remote,1)
  self.assertEqual(export_cloud(self.db)['deliveries'][0]['date'],'2026-09-17')

if __name__=='__main__':unittest.main()
