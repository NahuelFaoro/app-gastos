import json
import tempfile
import subprocess
import unittest
from pathlib import Path
from app.db import Database
from app.mobile_export import export_mobile

class ExportMobileTest(unittest.TestCase):
    def test_export_preserves_zone_rate_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp)/'test.db'); db.initialize()
            with db.connect() as con:
                zone = con.execute("INSERT INTO flex_zones(name) VALUES ('Zona temporal')").lastrowid
                con.executemany('INSERT INTO flex_zone_rates(zone_id, price, effective_from) VALUES (?,?,?)',
                    [(zone, 4990, '2026-01-01'), (zone, 5990, '2026-02-01')])
            exported = next(z for z in export_mobile(db)['zones'] if z['name'] == 'Zona temporal')
            self.assertEqual(exported['rates'], [{'date':'2026-01-01','amount':499000}, {'date':'2026-02-01','amount':599000}])

    def test_export_keeps_snapshot_and_excludes_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Database(Path(tmp)/'test.db');db.initialize()
            db.set_setting('mobile_pair_code','SECRET-NOT-EXPORTABLE')
            result=export_mobile(db)
            self.assertEqual(result['format'],'app-gastos-mobile')
            self.assertNotIn('SECRET-NOT-EXPORTABLE',json.dumps(result))
            self.assertNotIn('settings',result['desktop_snapshot'])
            self.assertEqual(len(result['categories']),len(result['desktop_snapshot']['categories']))
            parent_ids={r['id'] for r in result['categories']}
            self.assertTrue(all(not r['parent'] or r['parent'] in parent_ids for r in result['categories']))
            self.assertEqual(export_mobile(db)['accounts'],result['accounts'])
            check = subprocess.run(['node','--input-type=module','-e',"import {validate} from './mobile/model.mjs'; let text=''; for await (const chunk of process.stdin)text+=chunk; validate(JSON.parse(text));"], input=json.dumps(result),text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
            self.assertEqual(check.returncode,0,check.stderr)

if __name__=='__main__': unittest.main()
