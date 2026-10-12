"""Counter, boundary and missing-evidence regression tests (no hardware access)."""
import json
import hashlib
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from audit_performance import compare, main, parse_observation


def display(start, end, paints=10, uploads=True):
    result = (f'[display-perf] started_ms={start} ended_ms={end} seconds={(end-start)/1000:.3f} upload_bytes=100\n'
              f'[display-events] takes=99 uploads=12 new_paints={paints} swaps=15\n')
    if uploads:
        result += ''.join(f'[display-upload] camera={c} count=2 bytes=200\n' for c in range(1, 7))
    return result


def receipt(text):
    # Deliberately split a line across chunks, as SSH reads can do.
    return {'events': [{'state': 'observation_started', 'offset': 99, 'partial_first_line': False},
                       {'state': 'log_chunk', 'text': text[:50]},
                       {'state': 'log_chunk', 'text': text[50:]},
                        {'state': 'observed', 'seconds': 120, 'offset': 99, 'end_offset': 1000}]}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def refresh_log_counts(document):
    raw = ''.join(e.get('text', '') for e in document['events'] if e['state'] == 'log_chunk')
    end = document['events'][-1]
    end.update(bytes=len(raw.encode()), end_offset=end['offset'] + len(raw.encode()))


def exact_receipt(candidate=False, paints=None, completed=None, dma_bytes=None, failed=0):
    """board_session observe shape, split chunks and deliberately bogus rounded FPS."""
    text = display(1000, 121000, paints if paints is not None else 2400 if candidate else 1200)
    text += (f'[infer-perf] started_ms=1000 ended_ms=121000 seconds=120.000 '
             f'completed={completed if completed is not None else 1200 if candidate else 600} failed={failed} completed_fps=9999\n')
    for c in range(1, 7):
        text += (f'[capture-traffic] camera={c} started_ms=1000 ended_ms=121000 seconds=120.000 '
                 f'polls=120 frame_dmas=120 dma_bytes={dma_bytes if dma_bytes is not None else 60000 if candidate else 120000} '
                 'delivered_frames=120 unstable=0 read_errors=0\n')
        # This estimate is intentionally wildly different from the exact DMA.
        text += f'[capture] camera={c} delivered_fps=999\n[capture] camera={c} delivered_fps=999\n'
    spec = {'exe': '/build/candidate/detview' if candidate else '/build/original/detview',
            'sha256': ('c' if candidate else 'b') * 64,
            'overrides': {'DET_BENCH': '1', **({'DETVIEW_TEXTURE_RING': '3', 'DETVIEW_CAPTURE_MAX_FPS': '15'} if candidate else {})},
            'assets': {'/models/weights': 'd' * 64, '/models/instructions': 'e' * 64}}
    result = receipt(text)
    log = '/logs/candidate' if candidate else '/logs/original'
    result.update(schema=1, action='observe', status='success', log=log, spec=spec,
                  binding={'host': 'board', 'config_sha256': '1' * 64, 'baseline_sha256': '2' * 64,
                           'candidate_sha256': spec['sha256'], 'spec_sha256': digest(spec),
                           'argv_sha256': ('4' if candidate else '3') * 64, 'settings_sha256': '5' * 64})
    result['events'][0].update(monotonic=1, log=log)
    result['events'][-1].update(monotonic=121, bytes=len(text.encode()), end_offset=99 + len(text.encode()),
                                pid=200 if candidate else 100, starttime=999 if candidate else 888)
    return result


class AuditTests(unittest.TestCase):
    def test_exact_baseline_actual_dma_and_improvement(self):
        result = compare(exact_receipt(), exact_receipt(True))
        comparison = result['comparison']
        self.assertTrue(comparison['accepted'])
        self.assertEqual(comparison['acceptance_reasons'], [])
        self.assertEqual(result['baseline']['inference']['completed'], 600)
        self.assertEqual(result['candidate']['inference']['completed'], 1200)
        self.assertEqual(comparison['successful_inference_fps']['baseline'], 5)
        payload = comparison['logical_capture_read_payload_bytes_per_second']
        self.assertEqual(payload['status'], 'improved')
        self.assertEqual(payload['baseline'], 6000)
        self.assertEqual(payload['candidate'], 3000)
        self.assertEqual(payload['measurement'], 'exact_logical_dma')
        self.assertEqual(payload['per_camera']['1']['baseline'], 1000)
        self.assertEqual(comparison['physical_ddr_bandwidth'], 'unmeasured')
        self.assertIn('pixel parity', comparison['acceptance_scope'])

    def test_exact_baseline_regression_or_equality_rejects_performance(self):
        for options, metric, status in (({'paints': 1100}, 'fresh_video_fps', 'regressed'),
                                        ({'completed': 600}, 'successful_inference_fps', 'equal'),
                                        ({'dma_bytes': 240000}, 'logical_capture_read_payload_bytes_per_second', 'regressed')):
            with self.subTest(options=options):
                comparison = compare(exact_receipt(), exact_receipt(True, **options))['comparison']
                self.assertFalse(comparison['accepted'])
                self.assertEqual(comparison['acceptance_status'], 'performance_not_improved')
                self.assertEqual(comparison[metric]['status'], status)

    def test_failed_or_missing_failure_counts_never_accept(self):
        for candidate in (False, True):
            for failure in ('nonzero', 'missing', 'malformed', 'failed_receipt'):
                baseline, trial = exact_receipt(), exact_receipt(True)
                target = trial if candidate else baseline
                if failure == 'failed_receipt':
                    target['status'] = 'failed'
                else:
                    replacement = {'nonzero': 'failed=1', 'missing': '', 'malformed': 'failed=unknown'}[failure]
                    for event in target['events']:
                        if event['state'] == 'log_chunk':
                            event['text'] = event['text'].replace('failed=0', replacement)
                    refresh_log_counts(target)
                with self.subTest(candidate=candidate, failure=failure):
                    comparison = compare(baseline, trial)['comparison']
                    self.assertIsNone(comparison['accepted'])
                    self.assertTrue(comparison['acceptance_reasons'])
                    if failure == 'nonzero':
                        self.assertTrue(any('failures must be zero' in r for r in comparison['acceptance_reasons']))
                    elif failure in {'missing', 'malformed'}:
                        self.assertTrue(any('Missing exact successful inference/failure totals' in r for r in comparison['acceptance_reasons']))

    def test_boundary_failures_cannot_be_hidden_by_window_exclusion(self):
        for counter in ('failed=1', ''):
            trial = exact_receipt(True)
            trial['events'][-2]['text'] += ('[infer-perf] started_ms=120000 ended_ms=122000 seconds=2.000 '
                                           f'completed=10 {counter}\n')
            refresh_log_counts(trial)
            result = compare(exact_receipt(), trial)
            self.assertEqual(result['candidate']['inference']['completed'], 1200)
            self.assertIsNone(result['comparison']['accepted'])
            self.assertTrue(any('inference' in r for r in result['comparison']['acceptance_reasons']))

    def test_missing_pins_changed_settings_and_stale_generation(self):
        mutations = [lambda d: d.update(status='running'),
                     lambda d: d['binding'].update(settings_sha256='f' * 64),
                     lambda d: d['binding'].update(config_sha256='f' * 64),
                     lambda d: d['binding'].update(baseline_sha256='f' * 64),
                     lambda d: d['binding'].pop('argv_sha256'),
                     lambda d: d['spec'].update(assets={}),
                     lambda d: d['events'][0].update(log='/logs/stale'),
                     lambda d: d['events'][-1].update(offset=0),
                     lambda d: d['events'][-1].pop('starttime'),
                     lambda d: d['events'][-1].update(seconds=119),
                     lambda d: d['events'].insert(0, {'state': 'candidate_identity', 'pid': 200, 'starttime': 123})]
        for mutate in mutations:
            trial = exact_receipt(True)
            mutate(trial)
            comparison = compare(exact_receipt(), trial)['comparison']
            self.assertIsNone(comparison['accepted'])
            self.assertTrue(comparison['acceptance_reasons'])

    def test_changed_asset_pins_reject_even_with_consistent_spec_digest(self):
        trial = exact_receipt(True)
        trial['spec']['assets']['/models/weights'] = 'a' * 64
        trial['binding']['spec_sha256'] = digest(trial['spec'])
        comparison = compare(exact_receipt(), trial)['comparison']
        self.assertIsNone(comparison['accepted'])
        self.assertIn('Model asset pins missing or changed', comparison['acceptance_reasons'])

    def test_exact_six_camera_activity_must_overlap_for_acceptance(self):
        trial = exact_receipt(True)
        for event in trial['events']:
            if event['state'] == 'log_chunk':
                for c in range(1, 7):
                    old = f'[capture-traffic] camera={c} started_ms=1000 ended_ms=121000 seconds=120.000'
                    new = (f'[capture-traffic] camera={c} started_ms=1000 ended_ms=61000 seconds=60.000' if c == 1 else
                           f'[capture-traffic] camera={c} started_ms=61000 ended_ms=121000 seconds=60.000')
                    event['text'] = event['text'].replace(old, new)
        refresh_log_counts(trial)
        result = compare(exact_receipt(), trial)
        self.assertTrue(all(v['delivered_frames'] > 0 for v in result['candidate']['capture'].values()))
        self.assertFalse(result['candidate']['live_evidence']['completed_delivery_windows'])
        self.assertIsNone(result['comparison']['accepted'])

    def test_only_intentional_environment_changes_allowed(self):
        for key, value in (('DET_BENCH', '0'), ('MODEL', 'other'), ('DETVIEW_PROCESSING_MODE', 'other')):
            trial = exact_receipt(True)
            trial['spec']['overrides'][key] = value
            trial['binding']['spec_sha256'] = digest(trial['spec'])
            comparison = compare(exact_receipt(), trial)['comparison']
            self.assertIsNone(comparison['accepted'])
            self.assertTrue(any('Environment' in r or 'Unsupported' in r for r in comparison['acceptance_reasons']))
        trial = exact_receipt(True)
        trial['spec']['overrides']['DETVIEW_CAPTURE_MAX_FPS'] = 'nan'
        trial['binding']['spec_sha256'] = digest(trial['spec'])
        self.assertIsNone(compare(exact_receipt(), trial)['comparison']['accepted'])

    def test_summary_only_and_unsupported_exact_inference_evidence(self):
        trial = exact_receipt(True)
        trial['summary'] = {'completed': 1200, 'failed': 0, 'all_six_live': True}
        trial['events'] = [e for e in trial['events'] if e['state'] != 'log_chunk']
        self.assertIsNone(compare(exact_receipt(), trial)['comparison']['accepted'])
        trial = exact_receipt(True)
        for event in trial['events']:
            if event['state'] == 'log_chunk':
                event['text'] = event['text'].replace('completed=1200', 'attempted=1200')
        refresh_log_counts(trial)
        self.assertIsNone(compare(exact_receipt(), trial)['comparison']['accepted'])

    def test_historical_dma_stays_estimated_and_cannot_accept(self):
        source = Path(__file__).parent / 'baseline/runtime_120s.json'
        comparison = compare(json.loads(source.read_text(encoding='utf-8')), exact_receipt(True))['comparison']
        self.assertIsNone(comparison['accepted'])
        self.assertEqual(comparison['logical_capture_read_payload_bytes_per_second']['measurement'], 'estimated_historical_frame_payload')
        self.assertTrue(comparison['logical_capture_read_payload_bytes_per_second']['status'].startswith('estimated_'))

    def test_cli_accepts_instrumented_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, document in (('baseline.json', exact_receipt()), ('candidate.json', exact_receipt(True))):
                (root / name).write_text(json.dumps(document), encoding='utf-8')
            with patch.object(sys, 'argv', ['audit_performance.py', str(root / 'candidate.json'), '--baseline', str(root / 'baseline.json'), '--output', str(root / 'audit.json')]), contextlib.redirect_stdout(io.StringIO()):
                main()
            output = json.loads((root / 'audit.json').read_text(encoding='utf-8'))
            self.assertTrue(output['results'][0]['comparison']['accepted'])

    def test_real_baseline_counts_and_tdm_uncertainty(self):
        source = Path(__file__).parent / 'baseline/runtime_120s.json'
        baseline = parse_observation(json.loads(source.read_text(encoding='utf-8')))
        self.assertEqual(baseline['display']['window_count'], 62)
        self.assertEqual(baseline['display']['new_paints'], 7135)
        self.assertAlmostEqual(baseline['display']['seconds'], 313.896)
        self.assertAlmostEqual(baseline['display']['fresh_paint_fps'], 22.73045849580753)
        self.assertIsNone(baseline['inference']['completed_fps'])
        self.assertIsNone(baseline['tdm']['completed_fps'])
        self.assertEqual(baseline['tdm']['completed_delta'], 4660)
        lo, hi = baseline['tdm']['completed_fps_bounds']
        self.assertLess(lo, hi)
        self.assertTrue(baseline['all_six_live'])

    def test_offset_is_not_monotonic_and_counts_not_rounded_rates(self):
        text = display(1000, 2000, 999) + display(2000, 4000, 30) + display(4000, 5000, 999)
        result = parse_observation(receipt(text))
        self.assertIsNone(result['source_monotonic_bounds_seconds'])
        self.assertEqual(result['display']['fresh_paint_fps'], 15)
        self.assertEqual(result['display']['camera_upload_payload_bytes_per_second'], 600)

    def test_boundary_and_incomplete_association(self):
        text = display(1000, 3000) + display(3000, 4000, uploads=False) + display(4000, 5000) + display(5000, 7000)
        result = parse_observation({'segment_text': text, 'start': {'monotonic': 2}, 'end': {'monotonic': 6}})
        self.assertEqual(result['display']['window_count'], 1)
        self.assertEqual(result['display']['windows'][0]['started_ms'], 4000)
        self.assertEqual(len(result['exclusions']), 3)

    def test_exact_inference_and_six_camera_completed_traffic(self):
        text = ''
        for start in (1000, 2000, 3000):
            text += f'[infer-perf] started_ms={start} ended_ms={start+1000} seconds=1.000 completed=17 failed=2 completed_fps=999\n'
            for c in range(1, 7):
                text += (f'[capture-traffic] camera={c} started_ms={start} ended_ms={start+1000} seconds=1.000 '
                         'polls=30 frame_dmas=25 dma_bytes=1000 delivered_frames=23 unstable=2 read_errors=1 maximum_fps=30\n')
        result = parse_observation(receipt(text))
        self.assertEqual(result['inference']['completed_fps'], 17)
        self.assertEqual(result['inference']['failed'], 2)
        self.assertTrue(result['all_six_live'])
        for camera in result['capture'].values():
            self.assertEqual(camera['frame_dmas'], 25)
            self.assertEqual(camera['dma_bytes_per_second'], 1000)
            self.assertEqual(camera['read_errors'], 1)

    def test_missing_actual_baseline_never_accepts(self):
        baseline = {'segment_text': display(1000, 2000) + display(2000, 3000),
                    'start': {'monotonic': 1}, 'end': {'monotonic': 3}}
        result = compare(baseline, receipt(''))
        self.assertIsNone(result['comparison']['accepted'])
        self.assertEqual(result['comparison']['successful_inference_fps']['status'], 'unavailable')
        self.assertFalse(result['comparison']['all_six_live'])

    def test_disjoint_camera_activity_does_not_establish_six_live(self):
        text = ''
        for c in range(1, 7):
            start = c * 2000
            text += (f'[capture-traffic] camera={c} started_ms={start} ended_ms={start+1000} seconds=1.000 '
                     'polls=1 frame_dmas=1 dma_bytes=100 delivered_frames=1 unstable=0 read_errors=0\n')
        result = parse_observation({'segment_text': text, 'start': {'monotonic': 1}, 'end': {'monotonic': 14}})
        self.assertFalse(result['all_six_live'])
        self.assertEqual(result['live_evidence']['common_delivery_intervals_ms'], [])

    def test_partial_lines_duplicate_windows_and_counter_reset(self):
        d = receipt('partial\n' + display(1000, 2000) + display(2000, 3000) + display(2000, 3000) + display(3000, 4000) + '[infer-perf] started_ms=4000')
        d['events'][0]['partial_first_line'] = True
        result = parse_observation(d)
        self.assertEqual(result['inference']['window_count'], 0)
        self.assertEqual(result['display']['window_count'], 0)
        source = {'segment_text': '[tdm] completed=20\n' + display(1000, 2000) + '[tdm] completed=5\n' + display(2000, 3000),
                  'start': {'monotonic': 1}, 'end': {'monotonic': 3}}
        self.assertIsNone(parse_observation(source)['tdm']['completed_fps_bounds'])


if __name__ == '__main__':
    unittest.main()
