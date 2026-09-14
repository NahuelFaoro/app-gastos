"""Exercise the actual Qt form and worker using synthetic credentials only."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from app.cloud_panel import CloudSyncPanel


class CloudLoginPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_failed_login_preserves_input_and_retry_clears_only_on_success(self):
        with patch('app.cloud_sync.keyring.get_password',return_value=None), \
             patch('app.cloud_sync.initialize_cloud_ids'), \
             patch('app.cloud_sync.meta',return_value=None), \
             patch('app.cloud_sync.keyring.set_password'):
            panel=CloudSyncPanel(SimpleNamespace(path=Path('synthetic.db')))
            panel.timer.stop()
            panel.email.setText(' Test@Example.Invalid ')
            password=' Synthetic-ñ-🔑-Test '
            panel.password.setText(password)
            response=Mock(ok=False,status_code=400,headers={'sb-request-id':'01234567-89ab-cdef-0123-456789abcdef'})
            response.json.return_value={'code':400,'error_code':'invalid_credentials'}
            try:
                with patch('app.cloud_sync.requests.request',return_value=response) as request:
                    QTest.mouseClick(panel.buttons[0],Qt.MouseButton.LeftButton)
                    self.wait_job(panel)
                    self.assertEqual(request.call_count,1)
                    self.assertEqual(request.call_args.kwargs['json'],{'email':'test@example.invalid','password':password})
                    self.assertIn('app-gastos-desktop/',request.call_args.kwargs['headers']['X-Client-Info'])
                    self.assertIn('01234567-89ab-cdef-0123-456789abcdef',panel.status.text())
                    self.assertEqual(panel.password.text(),password)
                    self.assertFalse(panel.password.isReadOnly())
                    response.ok=True
                    response.json.return_value={'user':{'id':'synthetic-user'},'expires_in':3600,'access_token':'synthetic-token','refresh_token':'synthetic-refresh'}
                    QTest.keyClick(panel.password,Qt.Key.Key_Return)
                    self.wait_job(panel)
                    self.assertEqual(request.call_count,2)
                    self.assertEqual(panel.password.text(),'')
                    self.assertIn('Sesión iniciada',panel.status.text())
            finally:
                panel.shutdown();panel.deleteLater();self.app.processEvents()

    def wait_job(self,panel):
        for _ in range(100):
            self.app.processEvents()
            if panel.job is None:return
            QTest.qWait(10)
        self.fail('Login worker did not finish')


if __name__=='__main__':unittest.main()
