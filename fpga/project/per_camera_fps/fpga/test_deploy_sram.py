"""Mutation guards for SRAM viewer pause; no SSH or hardware access."""
import unittest
from unittest.mock import Mock, patch
import deploy_sram as deploy


class Guards(unittest.TestCase):
    def setUp(self):
        self.ns = {'__name__': 'guard_test'}
        exec(deploy.motion.REMOTE_SOURCE.split("if __name__ == '__main__':", 1)[0], self.ns)
        self.target = dict(operation='old', pid=42, starttime='99', exe_sha256='a'*64)
        self.saved = dict(operation='old', boot_id='boot', config={'exe':'/pinned'}, baseline={})
        self.request = dict(action='pause_candidate', snapshot='/private', snapshot_sha256='a'*64,
                            start_operation='old', target=self.target)
        self.close, self.write, self.launch = Mock(), Mock(), Mock()
        self.mocks = dict(sha=lambda p:'a'*64, boot=lambda:'boot',
            private_read=Mock(side_effect=[self.saved, self.target]),
            close_exact=self.close, private_write=self.write, candidate_action=self.launch,
            verify_files=Mock(), process=Mock(return_value={'pid':42}))

    def assert_no_mutation(self):
        self.close.assert_not_called()
        self.write.assert_not_called()
        self.launch.assert_not_called()

    def test_hash_mismatch(self):
        self.mocks['sha'] = lambda p:'b'*64
        with patch.dict(self.ns, self.mocks), self.assertRaises(RuntimeError):
            self.ns['action'](self.request, Mock())
        self.assert_no_mutation()

    def test_exact_identity_mismatch(self):
        self.mocks['exact'] = Mock(side_effect=RuntimeError('identity mismatch'))
        with patch.dict(self.ns, self.mocks), self.assertRaises(RuntimeError):
            self.ns['action'](self.request, Mock())
        self.assert_no_mutation()

    def test_absent_viewer_with_owner(self):
        self.mocks.update(process=Mock(return_value=None), owners=lambda:[777])
        with patch.dict(self.ns, self.mocks), self.assertRaises(RuntimeError):
            self.ns['action'](self.request, Mock())
        self.assert_no_mutation()

    def test_receipt_target_mismatch(self):
        self.request['target'] = dict(self.target, pid=777)
        with patch.dict(self.ns, self.mocks), self.assertRaises(RuntimeError):
            self.ns['action'](self.request, Mock())
        self.assert_no_mutation()


if __name__ == '__main__':
    unittest.main()
