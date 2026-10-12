"""Meaningful offline negative semantics; no synthetic final-positive manifest."""
import copy
import json
from pathlib import Path
import py_compile
import struct
import subprocess
import sys
import tempfile
import unittest
from new_program_candidate import HERE, load, sha
from new_validate_board import (utc, identity_gate, screenshot_gate, screenshot_series,
                                progress_gate, reviewed_reference, vendor_parser, verify_document, program_time_gate)


class Gates(unittest.TestCase):
    def rejected(self, call, text):
        with self.assertRaisesRegex(ValueError, text):
            call()

    def identity(self):
        expected = {'board_id': 'semantic-board', 'host': 'semantic-host', 'boot_id': 'semantic-boot',
                    'exe': '/semantic/viewer', 'exe_sha256': 'a' * 64, 'argv': ['/semantic/viewer', '--fullscreen'],
                    'models': {'/semantic/model.rknn': 'b' * 64}}
        # Tiny /proc semantics fixture; never exported as board evidence.
        suffix = ['S'] + ['0'] * 18 + ['1000'] + ['0'] * 3
        snapshot = dict(expected, contract='viewerProcSnapshot/v1', pid=42, captured_utc='2026-01-01T00:00:20+00:00',
                        cmdline_hex=b'/semantic/viewer\0--fullscreen\0'.hex(),
                        proc_stat='42 (viewer with spaces) ' + ' '.join(suffix), clk_tck=100,
                        boot_unix=utc('2026-01-01T00:00:00+00:00'))
        return expected, snapshot, utc('2026-01-01T00:00:05+00:00')

    def test_identity_executable_timestamp_model_args(self):
        expected, snapshot, end = self.identity()
        identity_gate(snapshot, expected, end)
        for key, value, error in [('exe', '/wrong/viewer', 'executable'), ('exe_sha256', 'c' * 64, 'executable'),
                                  ('captured_utc', '2026-01-01T00:00:01+00:00', 'Viewer start'),
                                  ('models', {'/semantic/model.rknn': 'c' * 64}, 'model'),
                                  ('cmdline_hex', b'/semantic/viewer\0--wrong\0'.hex(), 'argv')]:
            bad = copy.deepcopy(snapshot)
            bad[key] = value
            self.rejected(lambda: identity_gate(bad, expected, end), error)
        self.rejected(lambda: identity_gate(snapshot, expected, end + 10), 'after actual programming')
        self.rejected(lambda: utc('2026-01-01T00:00:00'), 'Timezone')

    def test_actual_baseline_not_postprogram(self):
        files = {k: HERE / ('baseline.' + ext) for k, ext in [('png', 'png'), ('xwd', 'xwd'), ('metadata', 'json')]}
        meta = load(files['metadata'])
        captured = utc(meta['captured_utc'])
        ex = {'host': meta['host'], 'screen_geometry': [meta['width'], meta['height']]}
        # Actual baseline conversion can be read, but cannot satisfy future programming.
        _, parsed = screenshot_gate(dict(png='png', xwd='xwd', metadata='metadata'), files, ex, captured - 2, captured - 1)
        self.assertEqual(parsed['color_depth'], 24)
        self.assertIn(parsed['storage_bpp'], (24, 32))
        self.rejected(lambda: screenshot_gate(dict(png='png', xwd='xwd', metadata='metadata'), files, ex,
                                             captured + 1, captured + 2), 'predates')
        self.rejected(lambda: screenshot_series([{}], {}, {}, 0, 0, 0, 0), 'At least two')
        shot = dict(png='png', xwd='xwd', metadata='metadata')
        self.rejected(lambda: screenshot_series([shot, shot], files, ex, captured - 2, captured - 1,
                                              captured - 1, captured + 1), 'distinct')

    def test_storage_24_and_32_not_rgb_mode_inference(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for bpp in (24, 32):
                files = {k: root / (k + ext) for k, ext in [('png', '.png'), ('xwd', '.xwd'), ('metadata', '.json')]}
                header = [0] * 25
                header[:6] = [100, 7, 2, 24, 1, 1]
                header[7], header[11], header[12] = 0, bpp, 4
                header[14:17] = [0xff0000, 0xff00, 0xff]
                files['xwd'].write_bytes(struct.pack('>25I', *header) + bytes([3, 2, 1, 0]))
                Image.new('RGB', (1, 1), (1, 2, 3)).save(files['png'])
                meta = {'width': 1, 'height': 1, 'depth': 24, 'host': 'semantic-host',
                        'source': 'RK3568 X11 :0 root window', 'captured_utc': '2026-01-01T00:00:20+00:00',
                        'png': str(files['png']), 'xwd': str(files['xwd'])}
                files['metadata'].write_text(json.dumps(meta))
                shot = dict(png='png', xwd='xwd', metadata='metadata')
                ex = {'host': 'semantic-host', 'screen_geometry': [1, 1]}
                _, parsed = screenshot_gate(shot, files, ex, 0, 1)
                self.assertEqual(parsed['storage_bpp'], bpp)
                meta['depth'] = 32
                files['metadata'].write_text(json.dumps(meta))
                self.rejected(lambda: screenshot_gate(shot, files, ex, 0, 1), 'depth mismatch')
                meta['depth'] = 24
                files['metadata'].write_text(json.dumps(meta))
                Image.new('RGB', (1, 1), (9, 9, 9)).save(files['png'])
                self.rejected(lambda: screenshot_gate(shot, files, ex, 0, 1), 'differs')

    def test_false_progress_wrong_pid_exe_timestamp(self):
        expected, identity, end = self.identity()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'journal.jsonl'
            event = {'_PID': '42', '_EXE': expected['exe'], '_BOOT_ID': expected['boot_id'],
                     '__REALTIME_TIMESTAMP': str(int((end + 7) * 1000000)),
                     'MESSAGE': '[capture] camera=1 delivered_fps=10.00 tag_advance_rate=10.00 read_ms=1.000 frame_dma_ms=1.000 copy_ms=0.001 unstable=0'}
            for key, value, error in [('MESSAGE', event['MESSAGE'].replace('delivered_fps=10.00', 'delivered_fps=0.00'), 'False'),
                                     ('MESSAGE', event['MESSAGE'].replace('tag_advance_rate=10.00', 'tag_advance_rate=0.00'), 'False'),
                                     ('MESSAGE', event['MESSAGE'].replace('unstable=0', 'unstable=1'), 'False'),
                                     ('_PID', '43', 'PID'), ('_EXE', '/wrong', 'exe'),
                                     ('__REALTIME_TIMESTAMP', '1', 'timestamp')]:
                bad = dict(event)
                bad[key] = value
                path.write_text(json.dumps(bad) + '\n')
                self.rejected(lambda: progress_gate(path, identity, end + 5, end + 20), error)
            path.write_text(json.dumps(event) + '\n')
            rows, _ = progress_gate(path, identity, end + 5, end + 20)
            self.assertEqual(len(rows['1']), 1)
            self.assertFalse(rows['6'])  # Never silently infer six camera success.

    def test_pending_and_false_reference(self):
        self.rejected(lambda: reviewed_reference({'status': 'pending'}, {}, 'C6'), 'Pending')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'raw.txt'
            path.write_text('actual raw line\n')
            review = {'status': 'reviewed', 'reviewer': 'semantic-only', 'note': 'semantic test',
                      'references': [{'artifact': 'raw', 'line': 1, 'text': 'invented success'}]}
            self.rejected(lambda: reviewed_reference(review, {'raw': path}, 'diag'), 'reference mismatch')

    def test_legacy_and_prepare_cli_rejected(self):
        self.rejected(lambda: verify_document({'contract': 'boardValidation/v1', 'accepted': True}), 'v1 rejected')
        proc = subprocess.run([sys.executable, str(HERE / 'new_validate_board.py'), '--evidence',
                               str(HERE / 'board_validation_v2.prepare.json')], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(json.loads(proc.stdout)['status'], 'blocked')

    def test_actual_historical_cfg_parser(self):
        old = HERE.parent / 'run_20261006_134504_c9abdebb'
        parse, _ = vendor_parser()
        text = (old / 'log/cfg.log').read_bytes().decode('gb18030')
        stages, errors = parse(text, 'sram')
        self.assertFalse(errors)
        self.assertEqual(stages, load(old / 'receipt.json')['stages'])
        self.assertTrue(all(stages.values()))
        altered = text.replace('Executing : cfg_program -device_index 0 successfully.', 'missing program completion')
        self.assertFalse(all(parse(altered, 'sram')[0].values()))

    def test_program_time_raw_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {k: root / k for k in ('program_receipt', 'delivery', 'program_session_raw')}
            files['program_receipt'].write_text('{"semantic_only":true}')
            files['delivery'].write_text('{"semantic_only":true}')
            session = {'contract': 'programSession/v1', 'collector': 'semantic-only',
                       'started_utc': '2026-01-01T00:00:00+00:00', 'completed_utc': '2026-01-01T00:00:20+00:00',
                       'receipt_sha256': sha(files['program_receipt']), 'delivery_manifest_sha256': sha(files['delivery']),
                       'exit_code': 0, 'receipt_timezone': '+00:00'}
            files['program_session_raw'].write_text('\n'.join(f'{k}={session[k]}' for k in
                ('started_utc', 'completed_utc', 'receipt_sha256', 'delivery_manifest_sha256', 'exit_code')))
            pre = {'captured_unix': utc(session['started_utc']) - 10}
            program_time_gate(session, {}, pre, files)
            self.rejected(lambda: program_time_gate(session, {'updated': '2026-01-01 00:00:30'}, pre, files), 'Receipt timestamp')
            bad = dict(session, completed_utc='2026-01-01T00:00:19+00:00')
            self.rejected(lambda: program_time_gate(bad, {}, pre, files), 'raw timestamp')
            self.rejected(lambda: program_time_gate(session, {}, {'captured_unix': pre['captured_unix'] - 400}, files), 'chronology')


if __name__ == '__main__':
    for name in ('new_validate_board.py', 'collect_viewer_proc_v2.py', 'collect_program_session_v2.py', 'test_board_validation_v2.py'):
        py_compile.compile(str(HERE / name), doraise=True)
    unittest.main(verbosity=2)
