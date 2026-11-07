"""Actual trusted synthetic Git objects; no Docker or private filesystem reads."""
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from scripts import prepare_build_context


class BuildContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.addCleanup(self.tmp.cleanup)
        files={'app/server.py':'print("synthetic")','app/security.py':'# synthetic','app/runtime.py':'# synthetic',
               'deploy/Dockerfile':'ARG PYTHON_IMAGE\nFROM ${PYTHON_IMAGE}\nCOPY app/ /opt/app/\n',
               'deploy/base-image.lock.json':json.dumps({'base_image':'docker.io/library/python@sha256:'+'a'*64}),
               'web/index.html':'synthetic','web/app.js':'synthetic','web/style.css':'synthetic','scripts/restore_database.py':'# synthetic','README.md':'ignored build input'}
        for name,text in files.items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
        for command in (['git','init','--quiet'],['git','config','user.name','Synthetic'],['git','config','user.email','synthetic@example.invalid'],['git','add','--',*files],['git','commit','--quiet','-m','synthetic trusted release']):subprocess.run(command,cwd=self.root,check=True,capture_output=True)
    def test_context_is_minimal_and_identical_for_same_commit(self):
        one,manifest=prepare_build_context.create(self.root);two,other=prepare_build_context.create(self.root)
        self.assertEqual(one,two);self.assertEqual(manifest,other);self.assertFalse(manifest['image_built'])
        with tarfile.open(fileobj=io.BytesIO(one),mode='r:gz') as archive:
            names=archive.getnames();self.assertIn('Dockerfile',names);self.assertNotIn('README.md',names);self.assertNotIn('deploy/base-image.lock.json',names)
            for member in archive:self.assertTrue(member.isfile());self.assertEqual(member.mtime,0)
    def test_untracked_and_modified_worktree_content_are_never_read_into_context(self):
        (self.root/'app/server.py').write_text('uncommitted must not ship')
        (self.root/'app/untracked.py').write_text('untracked must not ship')
        (self.root/'local-notes.txt').write_text('untracked private synthetic')
        payload,_=prepare_build_context.create(self.root)
        with tarfile.open(fileobj=io.BytesIO(payload),mode='r:gz') as archive:
            self.assertEqual(archive.extractfile('app/server.py').read(),b'print("synthetic")')
            self.assertNotIn('app/untracked.py',archive.getnames());self.assertNotIn('local-notes.txt',archive.getnames())
    def test_missing_expected_source_or_base_digest_fails_closed(self):
        (self.root/'deploy/base-image.lock.json').write_text('{"base_image":"mutable:latest"}')
        subprocess.run(['git','add','deploy/base-image.lock.json'],cwd=self.root,check=True,capture_output=True);subprocess.run(['git','commit','--quiet','-m','bad fixture'],cwd=self.root,check=True,capture_output=True)
        with self.assertRaises(ValueError):prepare_build_context.create(self.root)
