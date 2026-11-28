"""Development listeners belong to reviewed previews, not contained CLI smoke tests."""
import json
from pathlib import Path
import tempfile
import unittest
from app import full_task

class WebSmokePlanTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name)
        (self.root/'package.json').write_text(json.dumps({'scripts':{'dev':'node server.js'}}))
        self.plan={'summary':'implement a web calculator','stack':'node','files':['server.js','calc.js','tests/calc.test.js'],
                   'test':'node-test','build':None,'smoke':{'argv':['node','server.js'],'expect':'ready'}}
        self.env={'node':True,'npm':True}

    def test_declared_server_cannot_be_selected_as_a_cli_smoke(self):
        with self.assertRaisesRegex(ValueError,'managed preview'):
            full_task.parse_plan(json.dumps(self.plan),'Implement the web calculator',self.root,self.env)

    def test_web_plan_can_use_independent_tests_then_a_separate_preview(self):
        self.plan['smoke']=None
        plan=full_task.parse_plan(json.dumps(self.plan),'Implement the web calculator',self.root,self.env)
        self.assertIsNone(plan['smoke']);self.assertEqual(plan['test'],'node --test')

    def test_web_terminal_start_instructions_do_not_force_a_cli_smoke(self):
        self.plan['smoke']=None
        result=full_task.parse_plan(json.dumps(self.plan),'Build a runnable web app and document the terminal launch command',self.root,self.env)
        self.assertIsNone(result['smoke'])

    def test_explicit_cli_still_requires_a_finite_smoke_even_with_a_web_view(self):
        self.plan['smoke']=None
        with self.assertRaisesRegex(ValueError,'smoke-test'):
            full_task.parse_plan(json.dumps(self.plan),'Build a CLI calculator with a web view',self.root,self.env)

    def test_separate_finite_cli_smoke_is_still_supported(self):
        self.plan['smoke']={'argv':['node','calc.js','2','3'],'expect':'5'}
        result=full_task.parse_plan(json.dumps(self.plan),'Implement a CLI calculator and web view',self.root,self.env)
        self.assertEqual(result['smoke']['entry'],'calc.js')

if __name__=='__main__':unittest.main()
