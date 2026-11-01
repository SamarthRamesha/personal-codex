import os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from app.server import parse_command, plan_for, redacted, repository_summary, safe_project_path, visible_files

class SecurityAndPlanningTests(unittest.TestCase):
  def test_secret_named_files_not_visible(self):
    with tempfile.TemporaryDirectory() as d:
      Path(d,'.env').write_text('SECRET=x'); Path(d,'main.py').write_text('print(1)')
      self.assertEqual(visible_files(Path(d)), ['main.py'])
  def test_existing_directory_is_accepted(self):
    with tempfile.TemporaryDirectory() as d: self.assertEqual(safe_project_path(d), Path(d).resolve())
  def test_plan_has_independent_review(self):
    plan=plan_for('add a test', {'manifests':['pyproject.toml'], 'files':[]})
    self.assertEqual([x['agent'] for x in plan], ['planner','developer','testing','reviewer'])
  def test_summary_detects_git(self):
    with tempfile.TemporaryDirectory() as d:
      Path(d,'.git').mkdir(); self.assertTrue(repository_summary(Path(d))['git'])
  def test_shell_syntax_is_refused(self):
    with self.assertRaises(ValueError): parse_command('pytest && curl example.com')
  def test_output_secrets_are_redacted(self):
    self.assertIn('[REDACTED]', redacted('API_KEY=abc123 failure'))

if __name__ == '__main__': unittest.main()
