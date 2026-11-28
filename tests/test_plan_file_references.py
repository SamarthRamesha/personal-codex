"""Bare filenames in diagnostics must not invent duplicate required root files."""
import json
from pathlib import Path
import tempfile
import unittest
from app import full_task


class PlanFileReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        (self.root/'tests').mkdir();(self.root/'tests/test_model.py').write_text('pass\n')
        self.plan={'summary':'repair','stack':'python','files':['model.py','tests/test_model.py'],
                   'test':'unittest','build':None,'smoke':None}

    def parsed(self,request):
        return full_task.parse_plan(json.dumps(self.plan),request,self.root,{'python3':True})['files']

    def test_unique_existing_test_basename_resolves_to_real_path(self):
        self.assertEqual(self.parsed('Repair model.py; test_model.py fails'),self.plan['files'])

    def test_explicit_relative_path_is_not_rewritten(self):
        self.assertIn('other/test_model.py',self.parsed('Create other/test_model.py'))

    def test_exact_root_file_takes_precedence(self):
        (self.root/'test_model.py').write_text('pass\n')
        self.assertIn('test_model.py',self.parsed('Inspect test_model.py'))

    def test_new_unmatched_filename_remains_required(self):
        self.assertIn('new_model.py',self.parsed('Create new_model.py'))

    def test_unique_planned_nested_filename_need_not_exist_yet(self):
        self.plan['files'].append('src/new_model.py')
        self.assertNotIn('new_model.py',self.parsed('Implement new_model.py'))

    def test_explicit_new_root_creation_cannot_be_relocated_by_the_plan(self):
        self.plan['files']=['src/model.py','tests/test_model.py']
        with self.assertRaisesRegex(ValueError,'root path'):
            self.parsed('Create model.py with the implementation')

    def test_explicit_root_creation_is_preserved_when_included_in_plan(self):
        self.assertIn('model.py',self.parsed('Create model.py with the implementation'))

    def test_ambiguous_basename_is_not_guessed(self):
        (self.root/'other').mkdir();(self.root/'other/test_model.py').write_text('pass\n')
        self.assertIn('test_model.py',self.parsed('Inspect test_model.py'))


if __name__=='__main__':unittest.main()
