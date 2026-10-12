"""Validate failure censoring, distinct attempts and raw log accounting."""
import unittest
import json
from pathlib import Path
from summarize_ioctl_stalls import summarize_text

class AttemptAccounting(unittest.TestCase):
    def test_success_alarm_and_errno_failure_are_distinct(self):
        raw = '\n'.join([
            '[diag] t=100.100 pango_ioctl cmd=c0045305 addr=0x00800000 len=614416 ms=40.000 rc=0 errno=11 alarm=0',
            '[diag] t=111.100 pango_ioctl cmd=c0045305 addr=0x00896000 len=16 ms=10000.000 rc=0 errno=11 alarm=1',
            '[diag] t=111.200 pango_ioctl cmd=c0045305 addr=0x00896000 len=16 ms=50.000 rc=-1 errno=110 alarm=0'])
        result = summarize_text(raw, 'synthetic')
        summary = result['summary']
        self.assertEqual(summary['logged_attempt_count'], 3)
        self.assertEqual(summary['logged_success_count'], 1)
        self.assertEqual(summary['logged_failure_count'], 2)
        self.assertEqual(summary['logged_failure_elapsed_ms'], 10050)
        self.assertEqual(summary['logged_success_elapsed_ms'], 40)
        attempts = result['attempts']
        self.assertFalse(attempts[0]['errno_valid'])
        self.assertFalse(attempts[1]['errno_valid'])
        self.assertTrue(attempts[2]['errno_valid'])
        self.assertEqual(attempts[1]['gap_from_previous_logged_completion_ms'], 1000)
        self.assertEqual([a['camera_from_address'] for a in attempts], [1, 1, 1])
        self.assertEqual(attempts[0]['rx_offset_under_retained_source'], '0x00000000')
        self.assertEqual(attempts[1]['rx_offset_under_retained_source'], '0x003ff000')
        self.assertIsNone(attempts[1]['rx_offset'])
        self.assertIsNone(summary['per_camera']['1']['true_all_attempt_mean_ms'])

    def test_retained_recovery_raw_crosscheck(self):
        root = Path(__file__).resolve().parents[3]
        path = root / 'log/100h_motion/pll56_deploy_a1b1cf04843840d7b699d2ba769443cc/recovery_observation.log'
        raw = path.read_text(encoding='utf-8')
        result = summarize_text(raw, str(path))
        self.assertEqual(len(result['attempts']), raw.count('pango_ioctl cmd='))
        self.assertEqual([a['line'] for a in result['attempts']], [5, 55, 66, 105, 165, 199])
        self.assertAlmostEqual(result['summary']['logged_failure_elapsed_ms'], 86989.608)
        self.assertEqual(result['attempts'][2]['requested_bytes'], 16)
        self.assertEqual(result['attempts'][2]['display_window']['stages']['gui_delay']['max_ms'], 21359)
        self.assertEqual(result['attempts'][3]['display_window']['stages']['camera_upload']['max_ms'], 11337.317)
        diagnosis = json.loads((root / 'log/100h_motion/readonly_diagnosis_20261004.json').read_text(encoding='utf-8'))
        full = summarize_text(diagnosis['full_recovery_log'], 'diagnosis')
        self.assertEqual(full['summary']['logged_failure_count'], 10)
        self.assertAlmostEqual(full['summary']['logged_failure_elapsed_ms'], 107838.420)

if __name__ == '__main__':
    unittest.main()
