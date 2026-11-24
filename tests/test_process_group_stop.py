"""Cancellation must stop owned descendants even when their group leader exits first."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from app import server


@unittest.skipUnless(hasattr(os, 'killpg'), 'requires Unix process groups')
class ProcessGroupStopTests(unittest.TestCase):
    def test_a_term_resistant_child_does_not_outlive_its_cooperative_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ready, heartbeat = root / 'ready', root / 'heartbeat'
            child_script = (
                "import os,signal,time,pathlib; "
                "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                f"pathlib.Path({str(ready)!r}).write_text(str(os.getpid())); "
                f"f=open({str(heartbeat)!r},'ab',buffering=0); "
                "end=time.monotonic()+20\n"
                "while time.monotonic()<end: f.write(b'x'); time.sleep(.03)\n")
            parent_script = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child_script!r}]); time.sleep(20)"
            parent = subprocess.Popen([sys.executable, '-c', parent_script], start_new_session=True,
                                      stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                deadline = time.monotonic() + 5
                while not ready.exists() and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue(ready.exists(), 'synthetic child never reported readiness')
                child_pid = int(ready.read_text())
                self.assertEqual(os.getpgid(child_pid), parent.pid, 'child must belong to the owned group')
                server.terminate_process_group(parent, grace=.15)
                self.assertIsNotNone(parent.poll(), 'the original process must be reaped')
                before = heartbeat.stat().st_size
                time.sleep(.3)
                self.assertEqual(heartbeat.stat().st_size, before,
                                 'the descendant is still writing after cancellation returned')
            finally:
                # Only the session/group created by this test is terminated. Both processes also
                # have a 20-second natural lifetime if the runner itself is killed unexpectedly.
                try: os.killpg(parent.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                parent.wait(timeout=5)

    def test_an_already_finished_group_is_safe_to_clean_up(self):
        process = subprocess.Popen([sys.executable, '-c', 'pass'], start_new_session=True)
        process.wait(timeout=5)
        start = time.monotonic()
        server.terminate_process_group(process, grace=.15)
        self.assertLess(time.monotonic() - start, 1)
