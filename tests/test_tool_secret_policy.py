"""The direct tool path must refuse the secret-shaped files context selection omits."""
from pathlib import Path
import tempfile
import unittest

from app import context, tools


class ToolSecretPolicyTests(unittest.TestCase):
    names = ('secrets.json', 'config/credentials.yaml', 'credentials.toml', 'deploy.pem',
             'id_dsa', '.netrc', 'certs/PRIVATE.KEY', 'nested/store.p12')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in self.names:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('DISPOSABLE-SYNTHETIC-CREDENTIAL')
        (self.root / 'secret_parser.py').write_text('def parse(): pass\n')

    def test_direct_reads_cannot_reintroduce_files_omitted_from_context(self):
        for name in self.names:
            with self.subTest(name=name):
                self.assertTrue(context.is_ignored(name, []))
                with self.assertRaises(tools.ToolCallError):
                    tools.read_file(self.root, name, 2000)

    def test_tool_listing_does_not_publish_secret_shaped_names(self):
        result = tools.list_files(self.root, '.', 3, 100)
        serialized = str(result)
        for name in self.names:
            with self.subTest(name=name):
                self.assertNotIn(Path(name).name, serialized)
        self.assertIn('secret_parser.py', serialized)

    def test_patches_cannot_modify_secret_shaped_files(self):
        for name in self.names:
            with self.subTest(name=name), self.assertRaises(tools.ToolCallError):
                tools.apply_patch(self.root, name, 'DISPOSABLE-SYNTHETIC-CREDENTIAL', 'replacement',
                                  tools.file_sha256(self.root / name))
        self.assertEqual((self.root / 'deploy.pem').read_text(), 'DISPOSABLE-SYNTHETIC-CREDENTIAL')

    def test_secret_shaped_directories_do_not_expose_their_children(self):
        private = self.root / 'nested' / 'secrets.toml'
        private.mkdir()
        (private / 'notes.txt').write_text('DISPOSABLE-SYNTHETIC-CREDENTIAL')
        self.assertNotIn('notes.txt', str(tools.list_files(self.root, '.', 3, 100)))
        with self.assertRaises(tools.ToolCallError):
            tools.read_file(self.root, 'nested/secrets.toml/notes.txt', 2000)

    def test_ordinary_source_with_secret_in_its_name_remains_usable(self):
        self.assertIn('parse', tools.read_file(self.root, 'secret_parser.py', 2000)['text'])
