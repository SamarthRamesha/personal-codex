"""Existing model services must never become launcher-owned implicitly."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock,patch
spec=importlib.util.spec_from_file_location('offline_launcher',Path(__file__).resolve().parents[1]/'scripts/offline_workstation.py')
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)

class LauncherOwnershipTests(unittest.TestCase):
    def test_reuse_skips_only_the_model_port_and_keeps_backend_conflict_check(self):
        with patch.object(launcher.socket,'create_connection',side_effect=ConnectionRefusedError) as connect:
            launcher.require_free_ports(reuse_ollama=True)
        self.assertEqual([call.args[0][1] for call in connect.call_args_list],[launcher.BACKEND_PORT]*2)
        with patch.object(launcher.socket,'create_connection',return_value=MagicMock()):
            with self.assertRaisesRegex(ValueError,'in use'):launcher.require_free_ports(reuse_ollama=True)

    def test_reuse_never_spawns_or_stops_the_existing_ollama(self):
        with tempfile.TemporaryDirectory() as folder:
            data=Path(folder);(data/'owner.token').write_text('synthetic-launcher-token-00000000000')
            backend=MagicMock();backend.poll.return_value=0
            with patch.object(launcher.sys,'platform','darwin'),patch.object(launcher.sys,'argv',['launcher','--reuse-ollama','--backend-only','--data-dir',folder]),patch.object(launcher.shutil,'which',return_value='/trusted/ollama'),patch.object(launcher,'require_free_ports'),patch.object(launcher,'wait_ready'),patch.object(launcher,'get_json',side_effect=[{'version':'synthetic'},{'models':[{'name':'qwen3.5:9b'}]}]),patch.object(launcher.subprocess,'Popen',return_value=backend) as start:
                with self.assertRaisesRegex(RuntimeError,'exited'):launcher.main()
            self.assertEqual(start.call_count,1)
            self.assertTrue(start.call_args.args[0][-1].endswith('app/server.py'))
            backend.terminate.assert_not_called();backend.kill.assert_not_called()

if __name__=='__main__':unittest.main()
