import copy
import tempfile
import unittest
from pathlib import Path
from app.db import Database
from app.cloud_sync import CloudSync
from app.cloud_bridge import export_cloud


class CloudServiceTests(unittest.TestCase):
 def test_desktop_receives_mobile_edit_and_does_not_repeat_it(self):
  with tempfile.TemporaryDirectory() as tmp:
   db=Database(Path(tmp)/'test.db');db.initialize()
   service=CloudSync(db);service.session={'user':{'id':'test-user'}}
   stored=None
   def request(path,body=None,authenticated=False):
    nonlocal stored
    if body is None:return [copy.deepcopy(stored)] if stored else []
    revision=stored['revision'] if stored else 0
    if body['expected_revision']!=revision:return {'ok':False}
    stored={'revision':revision+1,'document':copy.deepcopy(body['payload'])}
    return {'ok':True,'revision':revision+1}
   service.request=request
   service.sync(enable=True)
   stored['document']['accounts'][0]['initial']=12345
   stored['revision']+=1
   service.sync()
   self.assertEqual(export_cloud(db)['accounts'][0]['initial'],12345)
   service.sync();before=stored['revision'];service.sync()
   self.assertEqual(stored['revision'],before)
   self.assertEqual(db.get_setting('cloud_enabled'),'1')


if __name__=='__main__':unittest.main()
