"""An unexpected handler error must still answer with bounded JSON, never a reset connection."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer

import app.server as server


class ErrorSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.old = (server.DATA, server.DB_PATH, server.STORE, server.AUTH)
        server.DATA = base / "data"
        server.DB_PATH = server.DATA / "test.db"
        server.STORE = server.Store()
        server.AUTH = server.security.OwnerAuth("")
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), server.App)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        server.STORE.close()
        server.DATA, server.DB_PATH, server.STORE, server.AUTH = self.old
        self.tmp.cleanup()

    def request(self, method, path):
        client = http.client.HTTPConnection("127.0.0.1", self.http.server_port, timeout=5)
        client.request(method, path, None, {"Content-Type": "application/json"})
        response = client.getresponse()
        result = (response.status, dict(response.getheaders()), response.read())
        client.close()
        return result

    def assertBoundedFailure(self, status, headers, body, expected):
        self.assertEqual(status, expected)
        self.assertEqual(headers["Content-Type"].split(";")[0], "application/json")
        self.assertEqual(json.loads(body), {"error": "Request failed; details withheld"})

    def test_a_get_route_that_raises_still_answers_json(self):
        with patch.object(server.maintenance, "diagnostics", side_effect=KeyError("unexpected")):
            status, headers, body = self.request("GET", "/api/diagnostics")
        self.assertBoundedFailure(status, headers, body, 500)

    def test_a_delete_route_that_raises_still_answers_json(self):
        with patch.object(server.conversations, "delete_conversation", side_effect=KeyError("unexpected")):
            status, headers, body = self.request("DELETE", "/api/conversations/00000000-0000-4000-8000-000000000000")
        self.assertBoundedFailure(status, headers, body, 500)


if __name__ == "__main__":
    unittest.main()
