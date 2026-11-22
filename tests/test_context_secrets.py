"""Secret-shaped project files never reach a model prompt, a search result or a read."""
from pathlib import Path
import tempfile
import unittest

from app import context


class ContextSecretTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        (self.root / "main.py").write_text("print('hello')\n")
        (self.root / "app_config.toml").write_text("x = 1\n")
        for name, body in {"secrets.json": '{"token": "sk-live-123"}\n',
                           "credentials.yaml": "password: hunter2\n",
                           "deploy.pem": "-----BEGIN PRIVATE KEY-----\n",
                           "id_dsa": "private\n",
                           ".env": "TOKEN=sk-live-456\n"}.items():
            (self.root / name).write_text(body)

    def test_walk_skips_secret_shaped_files(self):
        self.assertEqual(context.walk(self.root), ["app_config.toml", "main.py"])

    def test_read_text_and_search_refuse_them(self):
        for name in ("secrets.json", "credentials.yaml", "deploy.pem", "id_dsa", ".env"):
            self.assertIsNone(context.read_text(self.root, name))
        self.assertEqual(context.search(self.root, "sk-live")["matches"], [])
        self.assertEqual(context.search(self.root, "hunter2")["matches"], [])

    def test_a_task_about_secrets_never_selects_them(self):
        selection = context.select(self.root, "rotate the secrets and credentials handling", max_bytes=20000)
        paths = [snippet["path"] for snippet in selection["files"]]
        self.assertNotIn("secrets.json", paths)
        self.assertNotIn("credentials.yaml", paths)
        self.assertNotIn("sk-live-123", context.prompt_block(selection))


if __name__ == "__main__":
    unittest.main()
