import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from app.cloud_sync import CloudSync, cloud_error


class CloudAuthErrorsTests(unittest.TestCase):
    def test_specific_auth_failures_are_not_hidden_by_http_400(self):
        service=CloudSync(SimpleNamespace(path=Path('synthetic.db')))
        for code,expected in [('email_not_confirmed','todavía no está confirmado'),('invalid_credentials','cuenta de App Gastos'),('refresh_token_not_found','sesión guardada venció')]:
            response=Mock(ok=False,status_code=400)
            response.json.return_value={'error_code':code}
            with self.subTest(code=code),patch('app.cloud_sync.requests.request',return_value=response):
                with self.assertRaisesRegex(ValueError,expected):service.request('/auth/v1/token',{})

    def test_unknown_response_does_not_expose_arbitrary_server_content(self):
        response=Mock(status_code=400)
        response.json.return_value={'message':'private-server-detail'}
        self.assertNotIn('private-server-detail',cloud_error(response))
        response.json.side_effect=ValueError('not JSON')
        self.assertIn('HTTP 400',cloud_error(response))

    def test_empty_password_does_not_send_request(self):
        service=CloudSync(SimpleNamespace(path=Path('synthetic.db')))
        with patch('app.cloud_sync.requests.request') as request:
            with self.assertRaises(ValueError):service.login('test@example.invalid','')
            request.assert_not_called()


if __name__=='__main__':unittest.main()
