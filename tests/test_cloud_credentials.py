import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from app.cloud_sync import CloudSync


def synthetic_session(refresh='synthetic-refresh'):
    return {'access_token':'synthetic-jwt-'+'x'*1800,'refresh_token':refresh,
            'expires_in':3600,'expires_at':9999999999,
            'user':{'id':'synthetic-user','email':'test@example.invalid',
                    'user_metadata':{'irrelevant':'x'*5000}}}


class CloudCredentialsTests(unittest.TestCase):
    def service(self):return CloudSync(SimpleNamespace(path=Path('synthetic.db')))

    def test_large_session_fits_vault_and_restores_by_refresh(self):
        vault={}
        def write(service,user,value):
            if len(value.encode('utf-16-le'))>2560:raise OSError(1783,'CredWrite')
            vault[(service,user)]=value
        with patch('app.cloud_sync.keyring.set_password',side_effect=write), \
             patch('app.cloud_sync.keyring.get_password',side_effect=lambda s,u:vault.get((s,u))):
            session=synthetic_session()
            self.assertGreater(len(json.dumps(session).encode('utf-16-le')),2560)
            service=self.service();service._save_session(session)
            self.assertTrue(service.session_persistent)
            stored=json.loads(next(iter(vault.values())))
            self.assertNotIn('access_token',stored)
            self.assertNotIn('user_metadata',stored['user'])
            restarted=self.service();restarted.restore()
            renewed=synthetic_session('rotated-refresh')
            with patch.object(restarted,'request',return_value=renewed) as request:
                self.assertEqual(restarted.token(),renewed['access_token'])
                request.assert_called_once_with('/auth/v1/token?grant_type=refresh_token',{'refresh_token':'synthetic-refresh'})
            self.assertEqual(json.loads(next(iter(vault.values())))['refresh_token'],'rotated-refresh')

    def test_vault_failure_keeps_authenticated_session_in_memory(self):
        service=self.service()
        with patch.object(service,'request',return_value=synthetic_session()), \
             patch('app.cloud_sync.initialize_cloud_ids'),patch('app.cloud_sync.meta',return_value=None), \
             patch('app.cloud_sync.keyring.set_password',side_effect=OSError(1783,'CredWrite')):
            message=service.login('test@example.invalid','synthetic-password')
        self.assertIn('Sesión iniciada',message)
        self.assertIn('Windows no pudo recordar',message)
        self.assertFalse(service.session_persistent)
        self.assertEqual(service.session['user']['id'],'synthetic-user')

    def test_legacy_session_remains_readable(self):
        session=synthetic_session()
        with patch('app.cloud_sync.keyring.get_password',return_value=json.dumps(session)):
            service=self.service()
            self.assertEqual(service.restore(),session)
            self.assertEqual(service.token(),session['access_token'])


if __name__=='__main__':unittest.main()
