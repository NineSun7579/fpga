"""Pure rollback gate tests: never connect to a board or launch vendor tools."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import rollback_100h_motion as rollback


def log(target='PG2L100H', final='1', initial='1'):
    def scan(done):
        return ('Executing : cfg_scan_chain\n' + target + '\n'
                'This device configure situation (done bit): ' + done + '\n'
                'Executing : cfg_scan_chain successfully.\n')
    return (scan(initial) + 'Executing : cfg_program -device_index 0\n'
            'The done bit is 1\nCOMMAND[Program] execute successfully\n'
            'Executing : cfg_program -device_index 0 successfully.\n' + scan(final))


class RollbackTests(unittest.TestCase):
    def test_actual_baseline(self):
        bit, proof = rollback.evidence()
        self.assertEqual(rollback.programmer.sha(bit), rollback.BASELINE_SHA256)
        self.assertTrue(proof['manifest_sha256'])

    def test_wrong_hash(self):
        with patch.object(rollback.programmer, 'sha', return_value='0' * 64):
            with self.assertRaisesRegex(RuntimeError, 'baseline SHA256 mismatch'):
                rollback.evidence()

    def test_wrong_manifest_target(self):
        with patch.object(rollback.programmer, 'load', return_value={
                'baseline_sha256': rollback.BASELINE_SHA256,
                'baseline_bitstream': str(Path(__file__).resolve())}):
            with self.assertRaisesRegex(RuntimeError, 'path mismatch'):
                rollback.evidence()

    def test_parser_rejections(self):
        for text in (log(target='PG2L50H'), log(final='0'),
                     log(final=''), log(initial='0'),
                     log().rsplit('Executing : cfg_scan_chain', 2)[0]):
            with self.subTest(text=text):
                stages, errors = rollback.parse_log(text, 'sram')
                self.assertFalse(all(stages.values()) and not errors)
        stages, errors = rollback.parse_log(log(), 'sram')
        self.assertTrue(all(stages.values()))
        self.assertFalse(errors)

    def test_renderer_pre_done_before_write(self):
        text = rollback.script(rollback.BASELINE, 'sram', Path('cfg.log'))
        self.assertLess(text.index('initial target DONE'), text.index('cfg_assign_file'))
        self.assertIn('final target DONE', text)
        self.assertNotIn('flash', text)

    def test_check_no_process_socket_board_and_unique_receipts(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()), \
                patch.object(rollback, 'board_quiesced', side_effect=AssertionError('board')), \
                patch.object(rollback, 'run', side_effect=AssertionError('run')), \
                patch.object(rollback.programmer.subprocess, 'run', side_effect=AssertionError('process')), \
                patch.object(rollback.programmer.subprocess, 'Popen', side_effect=AssertionError('launch')), \
                patch.object(rollback.programmer.socket, 'socket', side_effect=AssertionError('socket')):
            for _ in range(2):
                self.assertEqual(rollback.main(['--check', '--log-dir', temp]), 0)
            receipts = list(Path(temp).glob('*/receipt.json'))
            self.assertEqual(len(receipts), 2)
            self.assertTrue(all(json.loads(p.read_text())['status'] == 'validated_only' for p in receipts))

    def test_execution_owner_failure_never_runs(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()), \
                patch.object(rollback, 'board_quiesced', side_effect=RuntimeError('DMA owner active')), \
                patch.object(rollback, 'board_lock', return_value=contextlib.nullcontext(SimpleNamespace(path='mock.json'))), \
                patch.object(rollback, 'run') as run:
            self.assertEqual(rollback.main(['--execute', '--log-dir', temp]), 1)
            run.assert_not_called()

    def test_private_runner_does_not_mutate_programmer(self):
        self.assertIs(rollback.run.__globals__['script'], rollback.script)
        self.assertIs(rollback.run.__globals__['parse_log'], rollback.parse_log)
        self.assertIsNot(rollback.programmer.run.__globals__['script'], rollback.script)


if __name__ == '__main__':
    unittest.main()
