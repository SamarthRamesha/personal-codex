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

    def test_alternating_rejected_proposals_stop_at_second_cycle(self):
        evidence = [{"type":"rejected", "proposal_fingerprint": key} for key in ("a", "b", "a")]
        evidence.insert(2, {"type":"inference", "metrics": {"client_duration_ms": 10}})
        saved = json.loads(json.dumps(evidence))
        self.assertEqual(full_task.proposal_cycle_period(saved, "b"), 2)
        self.assertEqual(full_task.proposal_cycle_period(saved[:2], "a"), 0)

    def test_three_step_cycle_and_near_cycle(self):
        evidence = [{"type":"tools", "proposal_fingerprint": key} for key in ("a", "b", "c", "a", "b")]
        self.assertEqual(full_task.proposal_cycle_period(evidence, "c"), 3)
        self.assertEqual(full_task.proposal_cycle_period(evidence, "d"), 0)

    def test_actual_content_progress_resets_alternating_history(self):
        evidence = [{"type":"rejected", "proposal_fingerprint": key} for key in ("a", "b")]
        evidence += [{"type":"tools", "proposal_fingerprint":"edit", "content_progress":True,
                      "changed":["main.py"], "hashes":{"main.py":"a"*64}},
                     {"type":"rejected", "proposal_fingerprint":"a"}]
        self.assertEqual(full_task.proposal_cycle_period(evidence, "b"), 0)

    def test_legacy_successful_edit_is_conservative_progress_boundary(self):
        evidence = [{"type":"rejected", "proposal_fingerprint":"a"},
                    {"type":"tools", "proposal_fingerprint":"b", "changed":["main.py"],
                     "hashes":{"main.py":"a"*64}},
                    {"type":"rejected", "proposal_fingerprint":"a"}]
        self.assertEqual(full_task.proposal_cycle_period(evidence, "b"), 0)

    def test_noop_write_does_not_reset_cycle(self):
        evidence = [{"type":"tools", "proposal_fingerprint":key, "content_progress":False,
                     "changed":["main.py"], "hashes":{"main.py":"a"*64}} for key in ("a","b","a")]
        self.assertEqual(full_task.proposal_cycle_period(evidence, "b"), 2)

    def test_immediate_repetition_and_bounded_tail(self):
        evidence = [{"type":"rejected", "proposal_fingerprint":"a"}]
        self.assertEqual(full_task.proposal_cycle_period(evidence, "a"), 1)
        evidence.extend({"type":"inference"} for _ in range(100))
        self.assertEqual(full_task.proposal_cycle_period(evidence, "a"), 0)

    def test_prompt_identifies_actual_existing_paths_without_placeholder_prefix(self):
        prompt = full_task.implementation_prompt('repair', {"files":["stats.py"],"summary":"repair","references":""},
                                                '', 'source', existing=['stats.py','tests/test_stats.py'])
        self.assertIn('["stats.py", "tests/test_stats.py"]', prompt)
        self.assertIn('Every tool belongs inside operations', prompt)
        self.assertNotIn('"path":"relative/', prompt)

    def test_successful_validation_enters_review_instead_of_replaying_edit_tutorial(self):
        prompt = full_task.implementation_prompt('repair', {"files":["stats.py"],"summary":"repair","references":""},
                                                'Verified', 'current source', verified=True, existing=['stats.py'])
        self.assertTrue(prompt.startswith('FINAL REVIEW'))
        self.assertIn('"status":"complete"', prompt)
        self.assertIn('Further edits invalidate the passed checks', prompt)
        self.assertNotIn('EXACT_EXISTING_PATH', prompt)


if __name__ == '__main__':
    unittest.main()
