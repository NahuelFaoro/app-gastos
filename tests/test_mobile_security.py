import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection, HTTPResponse
from pathlib import Path

from app.constants import APP_VERSION
from app.db import Database
from app.mobile_security import PairingLimiter
from app.mobile_server import MobileServer, _Handler, _HTTPServer, ensure_mobile_credentials


class PairingLimiterTests(unittest.TestCase):
    def test_window_expires_without_sleep(self):
        now = [0.0]
        limiter = PairingLimiter(clock=lambda: now[0])
        self.assertTrue(all(limiter.allow() for _ in range(5)))
        self.assertFalse(limiter.allow())
        now[0] = 60
        self.assertTrue(limiter.allow())

    def test_concurrent_attempts_share_limit(self):
        limiter = PairingLimiter()
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(lambda _: limiter.allow(), range(30))), 5)


class MobileHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Database(Path(self.tmp.name) / "mobile.db")
        self.db.initialize()
        self.token, self.code = ensure_mobile_credentials(self.db)
        self.server = _HTTPServer(("127.0.0.1", 0), _Handler)
        self.server.app_server = MobileServer(self.db)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path, body=None, authenticated=False, headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        request_headers = {"Content-Type": "application/json"}
        if authenticated:
            request_headers["X-AppGastos-Token"] = self.token
        request_headers.update(headers or {})
        try:
            # Cabeceras y cuerpo juntos: los casos de rechazo temprano no deben
            # intentar enviar otro paquete después del cierre del servidor.
            raw = body.encode("utf-8") if isinstance(body, str) else body or b""
            request_headers.setdefault("Content-Length", str(len(raw)))
            request_headers["Host"] = "127.0.0.1"
            message = f"{method} {path} HTTP/1.0\r\n"
            message += "".join(f"{key}: {value}\r\n" for key, value in request_headers.items())
            connection.connect()
            connection.send(message.encode("latin-1") + b"\r\n" + raw)
            response = HTTPResponse(connection.sock)
            response.begin()
            return response.status, dict(response.getheaders()), json.loads(response.read())
        finally:
            connection.close()

    def test_pair_then_read_accounts_and_version(self):
        status, headers, body = self.request("POST", "/api/pair", json.dumps({"code": self.code}))
        self.assertEqual(status, 200)
        self.assertEqual(body["token"], self.token)
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(self.request("GET", "/api/accounts", authenticated=True)[0], 200)
        self.assertEqual(self.request("GET", "/api/ping")[2]["version"], APP_VERSION)

    def test_sixth_pairing_attempt_is_blocked(self):
        wrong = "000000" if self.code != "000000" else "111111"
        for _ in range(5):
            self.assertEqual(self.request("POST", "/api/pair", json.dumps({"code": wrong}))[0], 403)
        self.assertEqual(self.request("POST", "/api/pair", json.dumps({"code": self.code}))[0], 429)
        self.assertEqual(self.request("GET", "/api/accounts", authenticated=True)[0], 200)

    def test_authentication_precedes_body_read(self):
        for method in ("POST", "PUT"):
            # Un cliente no vinculado no puede obligar a esperar un cuerpo grande.
            self.assertEqual(self.request(method, "/api/transactions", headers={"Content-Length": "99999"})[0], 401)
        self.assertEqual(self.request("DELETE", "/api/transactions?id=1")[0], 401)

    def test_invalid_json_does_not_write_data(self):
        for raw in ("{", "[]", "null", '{"amount":NaN}', '{"amount":Infinity}', '{"amount":1e999}'):
            with self.subTest(raw=raw):
                self.assertEqual(self.request("POST", "/api/transactions", raw, True)[0], 400)
        self.assertEqual(self.db.transactions(), [])

    def test_content_type_and_length_limits(self):
        # Estos rechazos ocurren al leer cabeceras: no enviar un cuerpo después
        # de que el servidor cierre evita una carrera TCP de Windows en el test.
        self.assertEqual(self.request("POST", "/api/transactions", None, True,
                                     {"Content-Type": "text/plain", "Content-Length": "2"})[0], 415)
        self.assertEqual(self.request("PUT", "/api/transactions", None, True,
                                     {"Content-Length": "-1"})[0], 400)
        self.assertEqual(self.request("POST", "/api/pair", None,
                                     headers={"Content-Length": "1025"})[0], 413)

    def test_authenticated_write_still_works(self):
        data = dict(kind="expense", amount=2.675, account_id=self.db.accounts()[0]["id"],
                    category_id=self.db.categories("expense")[0]["id"], tx_date="2026-09-13")
        self.assertEqual(self.request("POST", "/api/transactions", json.dumps(data), True)[0], 201)
        self.assertEqual(self.db.transactions()[0]["amount"], 2.68)

    def test_non_ascii_credentials_are_rejected(self):
        self.assertEqual(self.request("POST", "/api/pair", json.dumps({"code": "１２３４５６"}))[0], 403)
        self.assertEqual(self.request("GET", "/api/accounts", headers={"X-AppGastos-Token": "é"})[0], 401)
