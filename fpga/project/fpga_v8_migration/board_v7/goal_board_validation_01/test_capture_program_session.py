"""All tests are local fakes; never call SSH or the real consumer."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import capture_program_session as c
from new_validate_board import program_time_gate


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.bit = self.root / 'actual.bit'
        self.bit.write_bytes(b'fake offline bit')
        self.manifest = self.root / 'manifest.json'
        self.pre = self.root / 'preflight.json'
        self.doc = dict(candidate_id='source_diagnostics_timing_build_03', limitations={},
                        bitstream=dict(path=str(self.bit), sha256=c.sha(self.bit), bytes=self.bit.stat().st_size))
        c.save(self.manifest, self.doc)
        c.save(self.pre, dict(captured_unix=time.time()))
        # Existing old receipt must never be selected.
        old = self.root / 'candidate_run_old'
        old.mkdir()
        c.save(old / 'receipt.json', dict(status='success'))

    def boot(self, directory):
        return dict(captured_utc=c.utc())

    def runner(self, command, **kwargs):
        self.assertEqual(command[-4:], ['--manifest', str(self.manifest), '--owner-preflight', str(self.pre)])
        folder = self.root / 'candidate_run_actual'
        folder.mkdir()
        (folder / 'validated_delivery.json').write_bytes(self.manifest.read_bytes())
        logs = [folder / name for name in ('cfg.log', 'server.log', 'client.log')]
        for path in logs:
            path.write_text('offline programmer fixture', encoding='utf-8')
        receipt = dict(status='success', mode='sram', target='PG2L100H', check_only=False,
                       board_operation_verified=False, candidate_id=self.doc['candidate_id'],
                       bit=str(self.bit), bit_sha256=self.doc['bitstream']['sha256'],
                       bit_bytes=self.bit.stat().st_size, delivery_manifest_sha256=c.sha(self.manifest),
                       owner_preflight_sha256=c.sha(self.pre), programmer_sha256=c.sha(c.VENDOR),
                       limitations={}, logs=[str(p) for p in logs], stages={'offline_stage': True},
                       retained_directory=str(folder))
        if self.variant == 'fail':
            receipt['status'] = 'FAIL'
        if self.variant == 'candidate':
            receipt['candidate_id'] = 'source_diagnostics_timing_build_02'
        if self.variant == 'schema':
            del receipt['bit_bytes']
        c.save(folder / 'receipt.json', receipt)
        stdout = 'vendor progress\n' + json.dumps(receipt, indent=2) + '\n'
        if self.variant == 'two_json':
            stdout += json.dumps(receipt)
        if self.variant == 'two_folders':
            (self.root / 'candidate_run_other').mkdir()
        if self.variant == 'bit_mutation':
            self.bit.write_bytes(b'mutated')
        if self.variant == 'receipt_mutation':
            c.save(folder / 'receipt.json', {**receipt, 'status': 'FAIL'})
        if self.variant == 'manifest_mutation':
            self.manifest.write_text('{}')
        if self.variant == 'raise':
            raise OSError('offline launch failure')
        return subprocess.CompletedProcess(command, 7 if self.variant == 'nonzero' else 0,
                                           stdout.encode('utf-8'), b'')

    def collect(self, variant='ok'):
        self.variant = variant
        with patch.object(c, 'vendor_parser', return_value=(lambda text, mode: ({'offline_stage': True}, []),
                                                           __import__('re').compile('ERROR'))):
            return c.execute(self.manifest, self.pre, self.root, self.boot, self.runner)

    def test_actual_boundaries_pass_existing_time_gate(self):
        code, directory = self.collect()
        self.assertEqual(code, 0, c.load(directory / 'program_session_failure.json') if code else '')
        session = c.load(directory / 'program_session.json')
        files = dict(program_receipt=Path(session['receipt_path']), delivery=self.manifest,
                     program_session_raw=directory / 'program_session_raw.txt')
        self.assertGreater(program_time_gate(session, c.load(files['program_receipt']), c.load(self.pre), files), 0)
        events = [json.loads(line) for line in (directory / 'program_session_events.jsonl').read_text().splitlines()]
        self.assertEqual([e['event'] for e in events], ['launch_boundary', 'exit_boundary'])
        self.assertEqual(session['raw_source_sha256'], c.sha(directory / 'program_session_events.jsonl'))
        self.assertNotIn('accepted', session)

    def test_bad_receipts_and_mutations_fail_with_actual_boundaries(self):
        for variant in ('fail', 'candidate', 'schema', 'two_json', 'two_folders', 'bit_mutation',
                        'receipt_mutation', 'manifest_mutation', 'nonzero', 'raise'):
            with self.subTest(variant=variant):
                # Separate inventories prevent cross-test fake candidate folders.
                fixture = CaptureTests()
                fixture.setUp()
                self.addCleanup(fixture.doCleanups)
                code, directory = fixture.collect(variant)
                self.assertEqual(code, 1)
                self.assertFalse((directory / 'program_session.json').exists())
                failure = c.load(directory / 'program_session_failure.json')
                self.assertIn('started_utc', failure)
                self.assertIn('completed_utc', failure)
                self.assertIn('completed_monotonic', failure)

    def test_default_check_no_calls_or_writes(self):
        before = list(self.root.iterdir())
        with patch.object(sys, 'argv', ['capture_program_session.py']), \
             patch.object(c, 'execute', side_effect=AssertionError('execute')), \
             patch.object(c, 'capture_boot', side_effect=AssertionError('SSH')), \
             patch.object(c, 'verify', side_effect=AssertionError('manifest')), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(c.main(), 0)
        self.assertEqual(before, list(self.root.iterdir()))

    def test_execute_requires_explicit_paths(self):
        with patch.object(sys, 'argv', ['capture_program_session.py', '--execute']), \
             contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            c.main()
        self.assertEqual(caught.exception.code, 2)

    def test_boot_raw_and_helper_binding_with_fake_ssh(self):
        boot_id = '12345678-1234-1234-1234-123456789abc'
        output = (boot_id + '\nRK3568\n' + c.utc() + '\n').encode()
        class Stream(io.BytesIO):
            channel = SimpleNamespace(recv_exit_status=lambda: 0)
        class Client:
            closed = False
            def exec_command(inner, command, **kwargs):
                self.assertEqual(command, c.BOOT_COMMAND)
                self.assertNotIn('/dev/', command)
                return None, Stream(output), Stream(b'')
            def close(inner):
                inner.closed = True
        client = Client()
        helper = SimpleNamespace(board_host=lambda: 'offline-host', ssh_connect=lambda: client)
        # Allow a measured interval around fake remote UTC without sleeping.
        with patch.dict(sys.modules, board_host=helper), \
             patch.object(c.time, 'monotonic', side_effect=[10.0, 11.0]):
            boot = c.capture_boot(self.root)
        self.assertTrue(client.closed)
        self.assertEqual((self.root / 'program_boot_raw.txt').read_bytes(), (boot_id + '\n').encode())
        self.assertEqual(boot['raw_sha256'], c.sha(self.root / 'program_boot_raw.txt'))
        self.assertEqual(boot['helper_sha256'], c.sha(c.HELPER))
        self.assertEqual(boot['ssh_host'], 'offline-host')
        self.assertEqual(boot['host'], 'RK3568')
        self.assertEqual(boot['uncertainty_seconds'], 1.0)


if __name__ == '__main__':
    unittest.main()
