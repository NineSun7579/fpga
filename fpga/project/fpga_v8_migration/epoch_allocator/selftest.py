"""Linux-only tests. Creates exclusively temporary test journals, no device I/O."""
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import allocate_epoch as epoch


def reserve(args):
    return epoch.allocate(*args)


class EpochTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='v8_epoch_selftest_')
        self.path = Path(self.temp.name) / 'epochs.json'
        self.domain = 'simulation-only-reset-domain'

    def tearDown(self):
        self.temp.cleanup()

    def test_01_missing_refuses_to_invent_epoch(self):
        with self.assertRaises(FileNotFoundError):
            epoch.allocate(self.path, self.domain)
        self.assertFalse(self.path.exists())

    def test_02_cross_process_serialized_and_restart(self):
        epoch.initialize(self.path, self.domain, 400)
        with ProcessPoolExecutor(max_workers=8) as workers:
            values = list(workers.map(reserve, [(self.path, self.domain)] * 64))
        self.assertEqual(sorted(values), list(range(401, 465)))
        self.assertEqual(epoch.allocate(self.path, self.domain), 465)

    def test_03_reinitialization_and_wrong_domain_refused(self):
        epoch.initialize(self.path, self.domain, 70)
        with self.assertRaises(FileExistsError):
            epoch.initialize(self.path, self.domain, 0)
        with self.assertRaises(ValueError):
            epoch.allocate(self.path, 'different-domain')
        self.assertEqual(epoch.allocate(self.path, self.domain), 71)

    def test_04_no_zero_or_wrap(self):
        epoch.initialize(self.path, self.domain, epoch.MAX_EPOCH-1)
        self.assertEqual(epoch.allocate(self.path, self.domain), epoch.MAX_EPOCH)
        with self.assertRaises(OverflowError):
            epoch.allocate(self.path, self.domain)

    def test_05_symlink_and_corruption_refused(self):
        real = self.path.with_name('other.json')
        epoch.initialize(real, self.domain, 100)
        self.path.symlink_to(real)
        with self.assertRaises(OSError):
            epoch.allocate(self.path, self.domain)
        self.path.unlink()
        for value in ['broken', '{"format":1,"domain":"simulation-only-reset-domain","last_reserved":true}',
                      '{"format":1,"domain":"simulation-only-reset-domain","last_reserved":-1}']:
            self.path.write_text(value)
            with self.assertRaises((ValueError, json.JSONDecodeError)):
                epoch.allocate(self.path, self.domain)
        self.assertEqual(epoch.allocate(real, self.domain), 101)

    def test_06_failed_commit_never_exposes_epoch(self):
        epoch.initialize(self.path, self.domain, 20)
        before = self.path.read_bytes()
        with patch.object(epoch.os, 'replace', side_effect=OSError('injected storage failure')):
            with self.assertRaises(OSError):
                epoch.allocate(self.path, self.domain)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(epoch.allocate(self.path, self.domain), 21)

    def test_07_directory_fsync_error_burns_possibly_committed_epoch(self):
        epoch.initialize(self.path, self.domain, 40)
        original = epoch.os.fsync
        calls = 0
        def fail_directory(fd):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('injected directory fsync failure')
            original(fd)
        with patch.object(epoch.os, 'fsync', side_effect=fail_directory):
            with self.assertRaises(OSError):
                epoch.allocate(self.path, self.domain)
        # It was never returned to the caller. If the entry survived, skip it.
        self.assertEqual(epoch.allocate(self.path, self.domain), 42)

    def test_08_lock_symlink_refused(self):
        other = self.path.with_name('unrelated')
        other.write_text('untouched')
        self.path.with_name(self.path.name + '.lock').symlink_to(other)
        with self.assertRaises(OSError):
            epoch.initialize(self.path, self.domain, 0)
        self.assertEqual(other.read_text(), 'untouched')


if __name__ == '__main__':
    epoch._require_linux()
    unittest.main(verbosity=2)
