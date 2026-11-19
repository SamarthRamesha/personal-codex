"""Multiple approved edits to one file retain sequential digest/race protection."""
from pathlib import Path
import tempfile
import unittest
from app import tools


class SequentialPatchTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name);(self.root/'source.py').write_text('one\ntwo\n')
        self.operations=[{'tool':'apply_patch','path':'source.py','old_text':'one','new_text':'first'},
                         {'tool':'apply_patch','path':'source.py','old_text':'two','new_text':'second'}]

    def test_two_edits_share_ordered_review_and_execution_without_planning_writes(self):
        bound=tools.bind_hashes(self.root,self.operations)
        self.assertEqual((self.root/'source.py').read_text(),'one\ntwo\n')
        self.assertNotEqual(bound[0]['expected_sha256'],bound[1]['expected_sha256'])
        review=tools.review_operations(self.root,bound)
        self.assertFalse(review['stale']);self.assertEqual(len(review['files']),2)
        self.assertTrue(tools.execute_operations(self.root,bound)['ok'])
        self.assertEqual((self.root/'source.py').read_text(),'first\nsecond\n')

    def test_second_patch_can_use_text_created_by_first_patch(self):
        self.operations[1].update(old_text='first',new_text='final')
        self.assertTrue(tools.execute_operations(self.root,tools.bind_hashes(self.root,self.operations))['ok'])
        self.assertEqual((self.root/'source.py').read_text(),'final\ntwo\n')

    def test_create_then_patch_is_reviewable_and_exclusive(self):
        ops=[{'tool':'create_file','path':'new.py','content':'old'},
             {'tool':'apply_patch','path':'new.py','old_text':'old','new_text':'new'}]
        bound=tools.bind_hashes(self.root,ops);self.assertFalse(tools.review_operations(self.root,bound)['stale'])
        self.assertFalse((self.root/'new.py').exists());self.assertTrue(tools.execute_operations(self.root,bound)['ok'])
        self.assertEqual((self.root/'new.py').read_text(),'new')
        with self.assertRaises(tools.ToolCallError):tools.bind_hashes(self.root,ops)

    def test_external_change_between_steps_stops_second_patch(self):
        bound=tools.bind_hashes(self.root,self.operations)
        def change(kind,index,operation,result):
            if kind=='finish' and index==0:(self.root/'source.py').write_text('external edit')
        result=tools.execute_operations(self.root,bound,on_event=change)
        self.assertFalse(result['ok']);self.assertEqual(result['operations'][1]['status'],'error')
        self.assertEqual((self.root/'source.py').read_text(),'external edit')

    def test_stale_initial_bytes_cannot_become_current_via_simulation(self):
        bound=tools.bind_hashes(self.root,self.operations);(self.root/'source.py').write_text('user change')
        self.assertTrue(tools.review_operations(self.root,bound)['stale'])
        result=tools.execute_operations(self.root,bound)
        self.assertEqual(result['operations'][1]['status'],'skipped')
        self.assertEqual((self.root/'source.py').read_text(),'user change')

    def test_repeated_create_refused_before_any_write(self):
        ops=[{'tool':'create_file','path':'new.py','content':'one'}, {'tool':'create_file','path':'new.py','content':'two'}]
        with self.assertRaises(tools.ToolCallError):tools.bind_hashes(self.root,ops)
        self.assertFalse((self.root/'new.py').exists())


if __name__=='__main__':unittest.main()
