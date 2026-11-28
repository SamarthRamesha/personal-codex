"""Selected npm distribution reads must work without opening a tool-cache parent."""
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import unittest
from app import local_runner

class ToolDistributionTests(unittest.TestCase):
    def test_profile_includes_only_selected_npm_package_and_executable(self):
        script=Path('/synthetic/tool-cache/node/lib/node_modules/npm/bin/npm-cli.js')
        profile=local_runner.profile((),(),(script,))
        self.assertIn(local_runner.matcher('subpath',script),profile)
        self.assertIn(local_runner.matcher('subpath',script.parent.parent),profile)
        self.assertNotIn(local_runner.matcher('subpath',script.parents[4]),profile)

    @unittest.skipUnless(platform.system()=='Darwin' and shutil.which('node'),'requires actual Mac boundary')
    def test_non_homebrew_npm_modules_work_but_sibling_data_is_denied(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();package=root/'tool-cache/lib/node_modules/npm'
            (package/'bin').mkdir(parents=True);(package/'lib').mkdir()
            (package/'lib/test.js').write_text("module.exports='modules loaded';")
            outside=root/'unrelated.txt';outside.write_text('SYNTHETIC-OUTSIDE')
            script=package/'bin/npm-cli.js'
            script.write_text("#!/usr/bin/env node\nconsole.log(require('../lib/test.js'));try{require('fs').readFileSync("+repr(str(outside))+");process.exit(23)}catch(e){if(e.code!=='EPERM')throw e;console.log('outside refused')}\n")
            script.chmod(0o700)
            command=local_runner.sandboxed([str(script)],reads=(),writes=(),programs=(local_runner.trusted_program('node'),))
            result=subprocess.run(command,env={'PATH':os.environ['PATH']},capture_output=True,text=True,timeout=8)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('modules loaded',result.stdout);self.assertIn('outside refused',result.stdout)

if __name__=='__main__':unittest.main()
