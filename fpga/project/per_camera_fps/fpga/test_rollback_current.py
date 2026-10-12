"""Verify fresh current-viewer guards fail before snapshot or window mutation."""
import unittest
from unittest.mock import Mock, patch
import rollback_current as rollback

ns = {'__name__': 'rollback_guard_tests'}
exec(compile(rollback.motion.REMOTE_SOURCE, '<remote rollback>', 'exec'), ns)

class Guards(unittest.TestCase):
    def check_blocked(self, owners, snap, expected=None):
        write, close, launch = Mock(), Mock(), Mock()
        request = dict(action='identity_snapshot', expected_hash=expected)
        with patch.dict(ns, owners=lambda: owners, process=lambda pid: snap,
                        private_write=write, close_window=close):
            with patch.object(ns['subprocess'], 'Popen', launch):
                with self.assertRaises(RuntimeError):
                    ns['action'](request, Mock())
        write.assert_not_called()
        close.assert_not_called()
        launch.assert_not_called()

    def test_multiple_owners(self):
        self.check_blocked([1, 2], None)

    def test_exited_owner(self):
        self.check_blocked([1], None)

    def test_wrong_executable(self):
        self.check_blocked([1], dict(exe='/tmp/detview'))

    def test_wrong_fresh_hash(self):
        exe = '/userdata/linaro/detview-calibration-work/build/detview'
        self.check_blocked([1], dict(exe=exe, argv=[exe], uid=0,
            environment={}, exe_sha256='b'*64), 'a'*64)

    def test_no_force_or_flash(self):
        self.assertNotIn('os.kill', rollback.EXTRA)
        self.assertNotIn('XTestFakeKeyEvent', rollback.EXTRA)
        self.assertEqual(rollback.OLD_HASH, 'e3da6e1fbc7d0bb2abcc2ee57342906e395fb74cecd1f3163e9ada33e89e96f7')

if __name__ == '__main__':
    unittest.main()
