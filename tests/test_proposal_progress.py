"""Identity ignores cosmetic wording and covers rejected proposals across resume."""
import json
import unittest
from app import full_task


class ProposalProgressTests(unittest.TestCase):
    def test_reordered_keys_or_summaries_cannot_evade_identity(self):
        one = '{"status":"continue","summary":"one","operations":[{"tool":"read_file","path":"main.py"}]}'
        two = '{"operations":[{"path":"main.py","tool":"read_file"}],"summary":"two","status":"continue"}'
        self.assertEqual(full_task.proposal_fingerprint(one), full_task.proposal_fingerprint(two))

    def test_changed_operations_are_distinct(self):
        self.assertNotEqual(full_task.proposal_fingerprint('{"operations":[{"path":"a"}]}'),
                            full_task.proposal_fingerprint('{"operations":[{"path":"b"}]}'))

    def test_rejected_progress_survives_serialization_and_interleaved_metrics(self):
        key = full_task.proposal_fingerprint('malformed synthetic private content')
        evidence = json.loads(json.dumps([{"type":"rejected","proposal_fingerprint":key}, {"type":"inference"}]))
        self.assertTrue(full_task.repeated_proposal(evidence, key))
        self.assertFalse(full_task.repeated_proposal(evidence, "b"*64))
        self.assertNotIn('synthetic', key)

    def test_no_prior_proposal_is_not_a_cycle(self):
        self.assertFalse(full_task.repeated_proposal([{"type":"baseline"}], "a"*64))

    def test_prompt_identifies_actual_existing_paths_without_placeholder_prefix(self):
        prompt = full_task.implementation_prompt('repair', {"files":["stats.py"],"summary":"repair","references":""},
                                                '', 'source', existing=['stats.py','tests/test_stats.py'])
        self.assertIn('["stats.py", "tests/test_stats.py"]', prompt)
        self.assertIn('Every tool belongs inside operations', prompt)
        self.assertNotIn('"path":"relative/', prompt)


if __name__ == '__main__':
    unittest.main()
