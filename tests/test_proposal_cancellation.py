"""An approved legacy proposal must stop before its next filesystem operation."""
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from app import server, tools
from tests import test_tools as fixtures


@unittest.skipUnless(os.getenv('PERSONAL_CODEX_HTTP_TESTS') == '1', 'requires an approved loopback listener')
class ProposalCancellationTests(unittest.TestCase):
    setUp = fixtures.AgentApiTests.setUp
    tearDown = fixtures.AgentApiTests.tearDown
    call = fixtures.AgentApiTests.call
    prepare = fixtures.AgentApiTests.prepare

    def approved(self):
        proposal = {'summary': 'Write two synthetic files', 'operations': [
            {'tool': 'create_file', 'path': 'first.txt', 'content': 'completed work'},
            {'tool': 'create_file', 'path': 'second.txt', 'content': 'must not run after stop'}]}
        tid, provider, workspace = self.prepare(proposal)
        _, request = self.call(f'/api/tasks/{tid}/agent/request', 'POST', {'provider_id': provider['id']})
        self.call(f"/api/approvals/{request['approval_id']}", 'PATCH', {'status': 'approved'})
        status, planned = self.call(f'/api/tasks/{tid}/agent/plan', 'POST', {'provider_id': provider['id']})
        self.assertEqual(status, 201)
        self.call(f"/api/approvals/{planned['approval_id']}", 'PATCH', {'status': 'approved'})
        return tid, Path(workspace['path'])

    def test_cancel_before_execution_prevents_all_file_operations(self):
        tid, root = self.approved()
        self.assertEqual(self.call(f'/api/tasks/{tid}/cancel', 'POST', {})[0], 202)
        status, result = self.call(f'/api/tasks/{tid}/agent/execute', 'POST', {})
        self.assertEqual(status, 200)
        self.assertFalse((root / 'first.txt').exists(), 'a cancelled proposal wrote its first file')
        self.assertFalse((root / 'second.txt').exists())
        self.assertEqual(result['status'], 'cancelled')
        self.assertTrue(result['cancelled'])
        self.assertEqual(self.call(f'/api/tasks/{tid}/agent/execute', 'POST', {})[0], 404)

    def run_stop_between_writes(self, shutdown=False):
        tid, root = self.approved()
        reached, release = threading.Event(), threading.Event()
        original = tools.create_file
        result, failures = [], []
        def first_write(*args):
            value = original(*args)
            if args[1] == 'first.txt':
                reached.set()
                if not release.wait(5):
                    raise AssertionError('test did not release the completed operation')
            return value
        def execute():
            try: result.append(self.call(f'/api/tasks/{tid}/agent/execute', 'POST', {}))
            except BaseException as error: failures.append(error)
        with patch.object(tools, 'create_file', side_effect=first_write):
            worker = threading.Thread(target=execute)
            worker.start()
            try:
                self.assertTrue(reached.wait(5), 'first synthetic operation never finished')
                if shutdown: server.STOPPING.set()
                else: self.assertEqual(self.call(f'/api/tasks/{tid}/cancel', 'POST', {})[0], 202)
            finally:
                release.set()
                worker.join(8)
                if shutdown: server.STOPPING.clear()
            self.assertFalse(worker.is_alive(), 'request did not finish after cancellation')
        if failures: raise failures[0]
        self.assertEqual((root / 'first.txt').read_text(), 'completed work')
        self.assertFalse((root / 'second.txt').exists(), 'a second mutation ran after cancellation')
        self.assertEqual(result[0][0], 200)
        self.assertEqual(result[0][1]['status'], 'cancelled')
        self.assertEqual([r['status'] for r in result[0][1]['results']], ['ok', 'cancelled'])
        self.assertEqual(self.call(f'/api/tasks/{tid}/agent/execute', 'POST', {})[0], 404)

    def test_concurrent_cancel_preserves_first_write_and_prevents_the_second(self):
        self.run_stop_between_writes()

    def test_shutdown_between_writes_prevents_the_next_mutation(self):
        self.run_stop_between_writes(shutdown=True)
