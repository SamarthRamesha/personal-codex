"""Real temporary directory permissions model the inspected unsafe parent; no server mutation."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts import deployment_preflight as preflight


class AnchorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name).resolve();self.addCleanup(self.tmp.cleanup)
        self.root=self.base/'PersonalCodex'
    def test_world_writable_nonsticky_parent_refused_before_credential_read(self):
        self.base.chmod(0o777)
        with patch.object(preflight.os,'open') as opened:
            with self.assertRaisesRegex(ValueError,'replaceable'):preflight.inspect_layout(self.root,os.getuid(),os.getgid())
            opened.assert_not_called()
    def test_protected_parent_and_sticky_shared_ancestor_are_accepted_without_writes(self):
        self.assertEqual(preflight.inspect_anchor(self.root,os.getuid())['anchor'],'pass')
        before=self.base.stat().st_mtime_ns
        self.base.chmod(0o1777)
        self.assertFalse(preflight.inspect_anchor(self.root,os.getuid())['shared_parent_mutated'])
        self.assertEqual(self.base.stat().st_mtime_ns,before)
        self.assertFalse(self.root.exists())
    def test_untrusted_ancestor_owner_refused(self):
        if os.getuid()==0:self.skipTest('needs nonroot fixture owner')
        with self.assertRaisesRegex(ValueError,'owner'):preflight.inspect_anchor(self.root,os.getuid()+1)
    def test_default_candidate_moves_out_of_replaceable_application_parent(self):
        settings={'PC_ROOT':'/DATA/PersonalCodex','PC_UID':'65532','PC_GID':'65532','PC_IMAGE':'sha256:'+'a'*64,'PC_ORIGIN':'https://synthetic.private.ts.net'}
        self.assertEqual(preflight.validate_settings(settings)[0],Path('/DATA/PersonalCodex'))
        with self.assertRaises(ValueError):preflight.validate_settings({**settings,'PC_ROOT':'/DATA/AppData/PersonalCodex'})
