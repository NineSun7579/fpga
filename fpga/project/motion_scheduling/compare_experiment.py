"""Offline comparison of same-binary board_viewer gating-off/on observations.

python compare_experiment.py OFF.json ON.json --off-start OFF_START.json \
    --on-start ON_START.json --output comparison.json
No lifecycle/SSH imports. Receipt consistency is checked, not authenticated.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import statistics
import sys

PARSER_PATH = Path(__file__).resolve().parents[1] / 'performance_100h/audit_performance.py'
_spec = importlib.util.spec_from_file_location('motion_offline_performance_parser', PARSER_PATH)
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def hash_ok(value):
    return bool(re.fullmatch(r'[0-9a-f]{64}', str(value)))


def events(document, state):
    return [e for e in document.get('events', []) if e.get('state') == state]


def unique(document, state):
    rows = events(document, state)
    require(len(rows) == 1, 'Expected unique ' + state)
    return rows[0]


def successful(document, action):
    require(document.get('schema') == 1 and document.get('action') == action and
            document.get('status') == 'success' and not document.get('error'),
            'Expected successful schema-1 ' + action + ' receipt')
    require(document.get('host'), 'Missing board host')
    require(not any(e.get('state') in ('failed', 'error') for e in document.get('events', [])),
            'Receipt contains failure event')


def start_identity(document):
    successful(document, 'start')
    require(re.fullmatch(r'[0-9a-f]{32}', str(document.get('operation', ''))), 'Invalid start operation')
    snap = unique(document, 'snapshot_saved')
    require(hash_ok(snap.get('snapshot_sha256')), 'Invalid snapshot pin')
    require(snap.get('snapshot') == '/userdata/linaro/100h_performance/motion_viewer_' +
            document['operation'] + '.snapshot.json', 'Snapshot operation/path mismatch')
    identity, started = unique(document, 'candidate_identity'), unique(document, 'started')
    require(document['events'][-1] == started, 'Start lacks final verified started event')
    for key in ('pid', 'starttime', 'exe_sha256'):
        require(identity.get(key) == started.get(key), 'Start identity mismatch: ' + key)
    require(type(started.get('pid')) is int and started['pid'] > 0 and
            str(started.get('starttime', '')).isdigit() and int(started['starttime']) > 0 and
            hash_ok(started.get('exe_sha256')), 'Invalid process generation/binary pin')
    require(started.get('log') == snap['snapshot'].replace('.snapshot.json', '.log'), 'Start log generation mismatch')
    return started


def validate_observe(document, start, start_path):
    successful(document, 'observe')
    identity = start_identity(start)
    require(document.get('host') == start['host'], 'Observation/start host mismatch')
    require(document.get('start_receipt_sha256') == sha_file(start_path), 'Observation/start receipt hash mismatch')
    lower, upper = unique(document, 'observation_started'), unique(document, 'observed')
    require(document['events'][-1] == upper, 'Observation lacks final verified endpoint')
    elapsed = upper['monotonic'] - lower['monotonic']
    require(math.isfinite(elapsed) and elapsed >= 120 and
            math.isfinite(upper['seconds']) and abs(elapsed - upper['seconds']) <= .0011,
            'Observation monotonic duration must be >=120 seconds')
    require(type(lower.get('partial_first_line')) is bool and lower.get('log') == identity['log'],
            'Missing partial-line evidence or wrong log generation')
    lo_index, hi_index = document['events'].index(lower), document['events'].index(upper)
    require(lo_index < hi_index, 'Observation endpoint order invalid')
    chunks = events(document, 'log_chunk')
    require(chunks and all(lo_index < i < hi_index for i, e in enumerate(document['events'])
                           if e.get('state') == 'log_chunk'), 'Log chunk outside observation')
    raw = ''.join(e['text'] for e in chunks)
    offset = audit._count(lower, 'offset')
    require(upper.get('offset') == offset and audit._count(upper, 'end_offset') - offset ==
            audit._count(upper, 'bytes') == len(raw.encode('utf-8')), 'Log offsets/bytes disagree')
    for key in ('pid', 'starttime'):
        require(upper.get(key) == identity[key], 'Observation process generation mismatch: ' + key)
    # board_viewer emits progress, not candidate_identity samples, during observe.
    # The remote loop checks exact identity every iteration and at the endpoint.
    progress = events(document, 'observation_progress')
    times = [e['monotonic'] for e in progress]
    require(len(times) >= 2 and all(math.isfinite(t) for t in times) and
            all(b > a for a, b in zip(times, times[1:])), 'Missing/invalid observation progress samples')
    require(times[0] <= lower['monotonic'] + 15 and times[-1] >= upper['monotonic'] - 20 and
            all(b - a <= 20 for a, b in zip(times, times[1:])), 'Observation progress coverage incomplete')
    for e in events(document, 'candidate_identity'):
        require(all(e.get(k) == identity[k] for k in ('pid', 'starttime', 'exe_sha256')),
                'Stale identity sample')
    return {'pid': identity['pid'], 'starttime': identity['starttime'],
            'binary_sha256': identity['exe_sha256'], 'seconds': elapsed,
            'progress_samples': len(times), 'explicit_identity_samples': len(events(document, 'candidate_identity')),
            'identity_verification': 'Remote exact() loop plus final PID/starttime; progress samples carry time only'}


def resolve_inherited(value, current):
    path = Path(value)
    candidates = [path, current.parent / path, current.parent / path.name]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise ValueError('Inherited start receipt unavailable: ' + str(value))


def start_chain(path):
    chain, seen = [], set()
    current = Path(path).resolve()
    while True:
        require(current not in seen, 'Inherited receipt cycle')
        seen.add(current)
        document = read_json(current)
        identity = start_identity(document)
        chain.append({'path': str(current), 'sha256': sha_file(current), 'document': document,
                      'binary_sha256': identity['exe_sha256']})
        inherited = document.get('inherited_start_receipt')
        if not inherited:
            require(hash_ok(document.get('build_receipt_sha256')), 'Root start lacks build receipt pin')
            break
        current = resolve_inherited(inherited, current)
        require(document.get('start_receipt_sha256') == sha_file(current), 'Inherited start hash mismatch')
        parent = read_json(current)
        require(parent.get('host') == document['host'], 'Inherited host mismatch')
        if start_identity(parent)['exe_sha256'] != identity['exe_sha256']:
            require(hash_ok(document.get('build_receipt_sha256')), 'Inherited binary changed without build receipt pin')
    return chain


def relation(off, on):
    return {'off': off, 'on': on, 'percent_change': (on / off - 1) * 100
            if off is not None and on is not None and off > 0 else None}


def extra_metrics(document):
    text, lower, upper, _ = audit._input(document)
    bench, bench_times, traffic, policy, completed = [], [], [], [], []
    observed_capture = {c: {'unstable': 0, 'read_errors': 0, 'records': 0} for c in audit.CAMERAS}
    for line in text.splitlines():
        values = audit._values(line)
        if line.startswith('[tdm_bench]'):
            timestamp, ms = float(values['t']), float(values['ms'])
            require(math.isfinite(timestamp) and math.isfinite(ms) and ms >= 0, 'Invalid inference service sample')
            if lower <= timestamp <= upper:
                bench.append(ms)
                bench_times.append(timestamp)
        elif line.startswith('[tdm]') and 'completed' in values:
            completed.append(audit._count(values, 'completed'))
        elif line.startswith('[capture-traffic]') and values.get('camera') in observed_capture:
            counts = observed_capture[values['camera']]
            counts['records'] += 1
            for key in ('unstable', 'read_errors'):
                counts[key] += audit._count(values, key)
        elif line.startswith('[motion-traffic]'):
            traffic.append(values)
        elif line.startswith('[motion-scheduling]'):
            policy.append(values)
    counters = ('polls', 'attempted_io_ops', 'completed_dma_bytes', 'errors',
                'sequence_gaps', 'sequence_resets', 'sequence_changed')
    require(all(b >= a for a, b in zip(bench_times, bench_times[1:])), 'Inference bench clock went backwards')
    require(all(b >= a for a, b in zip(completed, completed[1:])), 'Cumulative successful inference counter reset')
    metadata = {'measurement': 'Cumulative checkpoint deltas; endpoints have no timestamps, so no exact rate',
                'samples': len(traffic), 'first': traffic[0] if traffic else None,
                'last': traffic[-1] if traffic else None, 'deltas': {}}
    for key in counters:
        if traffic and all(key in v for v in traffic):
            counts = [audit._count(v, key) for v in traffic]
            require(all(b >= a for a, b in zip(counts, counts[1:])), 'Metadata counter reset: ' + key)
            metadata['deltas'][key] = counts[-1] - counts[0]
    scheduling_deltas = {}
    for key in ('static_deferred_frames', 'motion_triggered_completed', 'fallback_completed', 'periodic_completed'):
        if policy and all(key in v for v in policy):
            counts = [audit._count(v, key) for v in policy]
            require(all(b >= a for a, b in zip(counts, counts[1:])), 'Scheduling counter reset: ' + key)
            scheduling_deltas[key] = counts[-1] - counts[0]
    return {'infer_service_ms_median': statistics.median(bench) if bench else None,
            'infer_service_sample_count': len(bench), 'metadata_traffic': metadata,
            'capture_errors_all_complete_records': observed_capture,
            'tdm_completed_checkpoints': {'samples': len(completed), 'first': completed[0] if completed else None,
                                          'last': completed[-1] if completed else None,
                                          'delta': completed[-1] - completed[0] if len(completed) >= 2 else None,
                                          'monotonic': True, 'exact_fps': None},
            'scheduling_checkpoint_deltas': scheduling_deltas,
            'scheduling_first': policy[0] if policy else None,
            'scheduling_last': policy[-1] if policy else None}


def summarize(document):
    metrics = audit.parse_observation(document)
    require(not metrics['parse_errors'], 'Malformed metric records')
    require(all(e['reason'] == 'Boundary-straddling window' for e in metrics['exclusions']),
            'Missing, duplicate, overlapping or invalid complete metric windows')
    display, infer = metrics['display'], metrics['inference']
    require(display['window_count'] > 0, 'Missing exact display windows')
    require(infer['window_count'] > 0 and infer['observation_failure_counts_complete'],
            'Missing exact successful inference/failure windows; untimed tdm checkpoints cannot supply exact FPS')
    require(metrics['live_evidence']['completed_delivery_windows'], 'Missing overlapping six-camera capture windows')
    cameras = {}
    for camera in audit.CAMERAS:
        capture = metrics['capture'][camera]
        require(capture['window_count'] > 0, 'Missing exact capture windows: camera ' + camera)
        uploads = sum(w['camera_uploads'][camera]['count'] for w in display['windows'])
        cameras[camera] = {'display_upload_fps': uploads / display['seconds'],
                           'display_upload_count': uploads, 'display_window_seconds': display['seconds'],
                           'capture_delivered_fps': capture['delivered_frames_per_second'],
                           'successful_image_dma_fps': capture['frame_dmas_per_second'],
                           'logical_image_dma_MB_per_second': capture['dma_bytes_per_second'] / 1e6,
                           **{k: capture[k] for k in ('seconds', 'window_count', 'polls', 'frame_dmas',
                                                     'dma_bytes', 'delivered_frames', 'unstable', 'read_errors')}}
    return {'new_display_fps': display['fresh_paint_fps'],
            'completed_infer_fps': infer['completed_fps'],
            'logical_image_dma_MB_per_second': sum(c['logical_image_dma_MB_per_second'] for c in cameras.values()),
            'inference_failed_complete_windows': infer['failed'],
            'inference_failed_all_complete_records': infer['observed_failed'],
            'unstable_complete_windows': sum(c['unstable'] for c in cameras.values()),
            'read_errors_complete_windows': sum(c['read_errors'] for c in cameras.values()),
            'cameras': cameras, **extra_metrics(document), 'exact_metrics': metrics}


def compare(off_path, on_path, off_start_path, on_start_path, switch='gating'):
    off_doc, on_doc = read_json(off_path), read_json(on_path)
    off_chain, on_chain = start_chain(off_start_path), start_chain(on_start_path)
    starts = [off_chain[0]['document'], on_chain[0]['document']]
    setting = 'experiment_gating' if switch == 'gating' else 'experiment_hud_batch'
    event_setting = 'gating' if switch == 'gating' else 'hud_batch'
    for start, expected in zip(starts, (0, 1)):
        require(type(start.get(setting)) is int and start[setting] == expected,
                'Supplied experiment switch must be 0 for off and 1 for on')
        require(unique(start, 'snapshot_saved').get(event_setting) == expected, 'Remote switch event mismatch')
        if switch == 'hud':
            require(start.get('experiment_gating') == 1 and unique(start, 'snapshot_saved').get('gating') == 1,
                    'HUD experiment must retain motion gating')
    require(starts[0]['host'] == starts[1]['host'], 'Off/on board host mismatch')
    require(off_chain[0]['binary_sha256'] == on_chain[0]['binary_sha256'], 'Off/on binary SHA256 mismatch')
    require(on_chain[0]['document'].get('start_receipt_sha256') == off_chain[0]['sha256'],
            'On switch must directly inherit supplied off start receipt')
    identities = [validate_observe(doc, start, path) for doc, start, path in
                  zip((off_doc, on_doc), starts, (off_start_path, on_start_path))]
    off, on = summarize(off_doc), summarize(on_doc)
    changes = {key: relation(off[key], on[key]) for key in
               ('new_display_fps', 'completed_infer_fps', 'logical_image_dma_MB_per_second', 'infer_service_ms_median')}
    changes['cameras'] = {c: {k: relation(off['cameras'][c][k], on['cameras'][c][k]) for k in
                              ('display_upload_fps', 'capture_delivered_fps', 'successful_image_dma_fps',
                               'logical_image_dma_MB_per_second')} for c in audit.CAMERAS}
    limits = ['User scene varies between sequential observations; this is not a controlled scene experiment.',
              'Static gating skips work: lower completed inference FPS is not evidence of faster inference throughput.',
              'New display FPS counts composite renders with new content; per-camera display FPS counts texture uploads.',
              'Logical image DMA MB/s uses successful image DMA byte counters and decimal MB; metadata traffic is separate. Physical DDR bandwidth is unmeasured.',
              'Complete windows have stream-specific durations. Boundary-straddling windows are excluded.',
              'Untimed tdm cumulative completed checkpoints support rate bounds only; exact FPS comes from completed/failed infer-perf windows.',
              'Local receipts omit argv/environment/model asset maps. The successful remote switch/observe code verifies those against the saved private snapshot; local checks verify snapshot and receipt-chain pins, not their contents.',
              'Bench service median describes logged completed service samples, not wall-clock scheduling throughput.']
    return {'schema': 1, 'experiment': 'same_binary_' + switch + '_off_on',
            'verification': {'same_binary_sha256': off_chain[0]['binary_sha256'], 'gating': [0, 1],
                             'host': starts[0]['host'], 'observations': identities,
                             'start_chains': [[{k: v for k, v in row.items() if k != 'document'} for row in chain]
                                              for chain in (off_chain, on_chain)],
                             'configuration_scope': 'Remote pinned snapshot inheritance; local same-binary and hash-linked receipt chain'},
            'inputs': {k: {'path': str(p), 'sha256': sha_file(p)} for k, p in
                       zip(('off_receipt', 'on_receipt', 'off_start', 'on_start'),
                           (off_path, on_path, off_start_path, on_start_path))},
            'off': off, 'on': on, 'comparison': changes, 'limits': limits,
            'performance_improvement_claim': 'Not established by an uncontrolled off/on scene comparison'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('offreceipt', type=Path)
    parser.add_argument('onreceipt', type=Path)
    parser.add_argument('--off-start', required=True, type=Path)
    parser.add_argument('--on-start', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--switch', choices=['gating','hud'], default='gating')
    args = parser.parse_args()
    try:
        result = compare(args.offreceipt, args.onreceipt, args.off_start, args.on_start, args.switch)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(json.dumps({'comparison': result['comparison'],
                          'off_failures': {k: result['off'][k] for k in ('inference_failed_all_complete_records', 'unstable_complete_windows', 'read_errors_complete_windows')},
                          'on_failures': {k: result['on'][k] for k in ('inference_failed_all_complete_records', 'unstable_complete_windows', 'read_errors_complete_windows')},
                          'interpretation': result['performance_improvement_claim'], 'output': str(args.output)},
                         indent=2, allow_nan=False))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print('Comparison rejected: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
