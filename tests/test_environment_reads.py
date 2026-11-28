"""Readiness must bind the manifest it checks, using synthetic files only."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import environment


class ManifestBoundaryTests(unittest.TestCase):
    def test_hardlinked_manifest_is_not_disclosed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            outside = root / 'outside.json'
            outside.write_text(json.dumps({'scripts': {'dev': 'SYNTHETIC-OUTSIDE-VALUE'}}))
            project = root / 'project'
            project.mkdir()
            os.link(outside, project / 'package.json')
            self.assertNotIn('SYNTHETIC-OUTSIDE-VALUE', json.dumps(environment.inspect(project)))

    def test_replacement_after_metadata_check_is_not_followed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            project = root / 'project'
            project.mkdir()
            manifest = project / 'package.json'
            manifest.write_text('{}')
            outside = root / 'outside.json'
            outside.write_text(json.dumps({'scripts': {'dev': 'SYNTHETIC-OUTSIDE-VALUE'}}))
            original = Path.read_text
            def replace_before_read(path, *args, **kwargs):
                if path.name == 'package.json':
                    manifest.unlink()
                    manifest.symlink_to(outside)
                return original(path, *args, **kwargs)
            with patch.object(Path, 'read_text', replace_before_read):
                self.assertNotIn('SYNTHETIC-OUTSIDE-VALUE', json.dumps(environment.inspect(project)))


if __name__ == '__main__':
    unittest.main()
