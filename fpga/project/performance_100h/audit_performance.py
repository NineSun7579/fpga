"""Offline, pure performance audit of retained baseline and observation receipts.

CLI: python audit_performance.py candidate.json [candidate2.json ...] --output audit.json
No board access or lifecycle imports. Rates use exact counters over complete windows.
"""
import argparse
import bisect
import hashlib
import json
import math
from pathlib import Path
import re

CAMERAS = tuple(str(i) for i in range(1, 7))
FRAME_PAYLOAD_BYTES = 640 * 480 * 2 + 16
INTENTIONAL_OVERRIDES = {'DETVIEW_TEXTURE_RING', 'DETVIEW_CAPTURE_MAX_FPS'}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _receipt_evidence(document):
    """Validate the evidence retained by board_session, without board access.

    Matching config/baseline bindings pin original model/source arguments and the
    captured environment. board_session substitutes argv[0] for the pinned exe;
    its successful observe outcome verifies identity/environment/files throughout.
    This is receipt consistency checking, not independent receipt authentication.
    """
    reasons = []
    binding, spec = document.get('binding', {}), document.get('spec', {})
    if document.get('schema') != 1 or document.get('action') != 'observe' or document.get('status') != 'success' or document.get('error'):
        reasons.append('Missing successful board_session observe outcome')
    if not isinstance(binding, dict) or not isinstance(spec, dict):
        return ['Missing receipt bindings or executable/asset pins']
    for key in ('config_sha256', 'baseline_sha256', 'candidate_sha256', 'spec_sha256', 'argv_sha256', 'settings_sha256'):
        if not re.fullmatch(r'[0-9a-f]{64}', str(binding.get(key, ''))):
            reasons.append('Missing or invalid binding: ' + key)
    if not binding.get('host'):
        reasons.append('Missing board host binding')
    if binding.get('spec_sha256') != _digest(spec) or binding.get('candidate_sha256') != spec.get('sha256'):
        reasons.append('Executable/spec pins disagree with binding')
    if not isinstance(spec.get('exe'), str) or not spec['exe'].startswith('/'):
        reasons.append('Missing absolute executable identity')
    assets = spec.get('assets')
    if not isinstance(assets, dict) or not assets or any(not str(p).startswith('/') or not re.fullmatch(r'[0-9a-f]{64}', str(h)) for p, h in assets.items()):
        reasons.append('Missing or invalid model asset pins')
    if not isinstance(spec.get('overrides'), dict):
        reasons.append('Missing environment override evidence')
    else:
        for key, value in spec['overrides'].items():
            valid = isinstance(value, str) and bool(value) and not any(c in value for c in '\0\r\n')
            if valid and key == 'DETVIEW_TEXTURE_RING':
                valid = bool(re.fullmatch(r'[1-9][0-9]*', value))
            if valid and key == 'DET_BENCH':
                valid = value in {'0', '1'}
            if valid and key == 'DETVIEW_CAPTURE_MAX_FPS':
                try:
                    valid = math.isfinite(float(value)) and float(value) >= 0
                except ValueError:
                    valid = False
            if not valid:
                reasons.append('Invalid environment override: ' + key)
    events = document.get('events', [])
    starts = [e for e in events if e.get('state') == 'observation_started']
    ends = [e for e in events if e.get('state') == 'observed']
    if len(starts) != 1 or len(ends) != 1 or not events or events[-1].get('state') != 'observed':
        reasons.append('Missing unique final observation endpoint')
        return reasons
    start, end = starts[0], ends[0]
    try:
        duration = end['monotonic'] - start['monotonic']
        if not math.isfinite(duration) or duration < 120 or not math.isfinite(end['seconds']) or abs(duration - end['seconds']) > .0011:
            reasons.append('Observation must have verified monotonic duration >=120 seconds')
        if events.index(start) >= events.index(end) or any(e.get('state') == 'log_chunk' for e in events[:events.index(start)]):
            reasons.append('Log chunks are outside observation generation')
        offset, endpoint = _count(start, 'offset'), _count(end, 'end_offset')
        raw = ''.join(e.get('text', '') for e in events if e.get('state') == 'log_chunk')
        if end.get('offset') != offset or endpoint <= offset or endpoint - offset != _count(end, 'bytes') or len(raw.encode('utf-8')) != end['bytes']:
            reasons.append('Observation log offsets/bytes disagree')
        if start.get('log') != document.get('log') or not document.get('log') or not isinstance(start.get('partial_first_line'), bool):
            reasons.append('Missing or stale log generation identity')
        if _count(end, 'pid') <= 0 or _count(end, 'starttime') <= 0:
            reasons.append('Missing process generation identity')
        for event in events:
            if event.get('state') == 'candidate_identity' and any(event.get(k) != end.get(k) for k in ('pid', 'starttime')):
                reasons.append('Stale process generation')
        if any(e.get('state') in {'failed', 'error'} for e in events):
            reasons.append('Receipt contains failure events')
    except (KeyError, TypeError, ValueError):
        reasons.append('Incomplete observation timing/count/identity evidence')
    return reasons


def _values(line):
    return dict(re.findall(r'([\w.]+)=([^\s,]+)', line))


def _count(values, key):
    value = values.get(key, '')
    if not re.fullmatch(r'\d+', str(value)):
        raise ValueError('Missing or noninteger count: ' + key)
    return int(value)


def _window(values):
    start, end = _count(values, 'started_ms'), _count(values, 'ended_ms')
    seconds = float(values['seconds'])
    if end <= start or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('Invalid window')
    if abs(seconds - (end - start) / 1000) > 0.0011:
        raise ValueError('Window duration disagrees with timestamps')
    return start, end, (end - start) / 1000


def _input(document):
    """Raw chunk order is essential: grouped parse summaries lose associations."""
    if 'segment_text' in document:
        text = document['segment_text']
        start = document.get('start', {}).get('monotonic')
        end = document.get('end', {}).get('monotonic')
        return text.rsplit('\n', 1)[0], start, end, None
    events = document.get('events', [])
    started = next((e for e in events if e.get('state') == 'observation_started'), {})
    observed = next((e for e in reversed(events) if e.get('state') == 'observed'), {})
    text = ''.join(e.get('text', '') for e in events if e.get('state') == 'log_chunk')
    if started.get('partial_first_line'):
        text = text.split('\n', 1)[1] if '\n' in text else ''
    text = text.rsplit('\n', 1)[0] if '\n' in text else ''
    # observed.seconds is elapsed, not a CLOCK_MONOTONIC endpoint.
    return text, started.get('monotonic'), observed.get('monotonic'), observed.get('seconds')


def parse_observation(document):
    """Return retained windows, exact totals, exclusions and measurement limits."""
    text, lower, upper, observed_seconds = _input(document)
    bounded = lower is not None and upper is not None
    limits = []
    if not text:
        limits.append('No complete raw log records available; grouped summary/parse_summary metrics cannot recover display row associations or original checkpoint order.')
    if not bounded:
        limits.append('No source monotonic observation bounds: discard first window per stream; require a later same-stream window to bracket each retained window.')
    displays, inference = [], []
    traffic = {c: [] for c in CAMERAS}
    captures = {c: [] for c in CAMERAS}
    checkpoints, panes, errors = [], [], []
    active = None
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r'^\[([^]]+)\]', line)
        if not match:
            continue
        tag, v = match[1], _values(line)
        try:
            if tag == 'display-perf':
                active = {'values': v, 'line_index': index, 'events': [], 'uploads': []}
                displays.append(active)
            elif tag == 'display-events' and active is not None:
                active['events'].append(v)
            elif tag == 'display-upload' and active is not None:
                active['uploads'].append(v)
            elif tag == 'infer-perf':
                inference.append({'values': v, 'line_index': index})
            elif tag == 'capture-traffic' and v.get('camera') in traffic:
                traffic[v['camera']].append({'values': v, 'line_index': index})
            elif tag == 'capture' and v.get('camera') in captures:
                captures[v['camera']].append(v)
            elif tag == 'tdm' and 'completed' in v:
                checkpoints.append({'completed': _count(v, 'completed'), 'line_index': index})
            elif tag == 'panes':
                panes.append(v)
        except (ValueError, KeyError) as exc:
            errors.append({'line_index': index, 'reason': str(exc)})

    exclusions = []

    def select(rows, name, keys, display=False):
        valid = []
        for position, row in enumerate(rows):
            v = row['values']
            try:
                start, end, seconds = _window(v)
                if bounded:
                    if start < lower * 1000 or end > upper * 1000:
                        raise ValueError('Boundary-straddling window')
                elif position == 0 or position == len(rows) - 1:
                    raise ValueError('Unbracketed boundary window')
                else:
                    previous = _window(rows[position - 1]['values'])
                    following = _window(rows[position + 1]['values'])
                    if start < previous[1] or end > following[0]:
                        raise ValueError('Overlapping or unordered neighbor windows')
                counts = {k: _count(v, k) for k in keys}
                item = {'started_ms': start, 'ended_ms': end, 'seconds': seconds,
                        'line_index': row['line_index'], **counts}
                if display:
                    if len(row['events']) != 1:
                        raise ValueError('Missing or duplicate display-events')
                    item.update({k: _count(row['events'][0], k) for k in ('takes', 'uploads', 'new_paints', 'swaps')})
                    uploads = row['uploads']
                    if len(uploads) != 6 or {u.get('camera') for u in uploads} != set(CAMERAS):
                        raise ValueError('Missing or duplicate six-camera display-upload rows')
                    item['camera_uploads'] = {u['camera']: {'count': _count(u, 'count'), 'bytes': _count(u, 'bytes')} for u in uploads}
                if valid and start < valid[-1]['ended_ms']:
                    raise ValueError('Overlapping or duplicate window')
                valid.append(item)
            except (ValueError, KeyError, TypeError) as exc:
                exclusions.append({'stream': name, 'line_index': row['line_index'], 'reason': str(exc)})
        return valid

    def totals(rows, keys):
        seconds = sum(r['seconds'] for r in rows)
        return {'windows': rows, 'window_count': len(rows), 'seconds': seconds,
                **{k: sum(r[k] for r in rows) for k in keys},
                **{k + '_per_second': sum(r[k] for r in rows) / seconds if seconds else None for k in keys}}

    dw = select(displays, 'display', ('upload_bytes',), True)
    display = totals(dw, ('takes', 'uploads', 'new_paints', 'swaps', 'upload_bytes'))
    display['fresh_paint_fps'] = display['new_paints_per_second']
    display['camera_upload_payload_bytes_per_second'] = (
        sum(u['bytes'] for r in dw for u in r['camera_uploads'].values()) / display['seconds'] if dw else None)
    infer = totals(select(inference, 'inference', ('completed', 'failed')), ('completed', 'failed'))
    infer['completed_fps'] = infer['completed_per_second']
    # Excluding a boundary window must not conceal failed runOnce calls or an
    # unsupported counter schema present in complete records of this observation.
    failure_counts = []
    for row in inference:
        try:
            failure_counts.append(_count(row['values'], 'failed'))
        except ValueError:
            pass
    infer['observation_failure_counts_complete'] = bool(inference) and len(failure_counts) == len(inference)
    infer['observed_failed'] = sum(failure_counts)
    camera_metrics = {}
    for camera in CAMERAS:
        camera_metrics[camera] = totals(select(traffic[camera], 'capture-' + camera,
            ('polls', 'frame_dmas', 'dma_bytes', 'delivered_frames', 'unstable', 'read_errors')),
            ('polls', 'frame_dmas', 'dma_bytes', 'delivered_frames', 'unstable', 'read_errors'))
        samples = captures[camera][1:]  # un-timed first aggregate can straddle start
        rates = [float(v['delivered_fps']) for v in samples if 'delivered_fps' in v]
        camera_metrics[camera]['sampled_delivered_fps_mean'] = sum(rates) / len(rates) if rates else None
        camera_metrics[camera]['sample_count'] = len(rates)
    # Each cumulative checkpoint lies between adjoining display emission times.
    # This bounds elapsed time; it does not assign a fabricated timestamp to a line.
    anchors = []
    for row in displays:
        try:
            anchors.append((row['line_index'], _window(row['values'])[1]))
        except (ValueError, KeyError):
            pass
    positions = [a[0] for a in anchors]
    timed = []
    for row in checkpoints:
        i = bisect.bisect_left(positions, row['line_index'])
        lo = anchors[i - 1][1] if i else (lower * 1000 if bounded else None)
        hi = anchors[i][1] if i < len(anchors) else (upper * 1000 if bounded else None)
        if lo is not None and hi is not None and lo <= hi:
            if bounded:
                lo, hi = max(lo, lower * 1000), min(hi, upper * 1000)
            if lo <= hi:
                timed.append({**row, 'earliest_ms': lo, 'latest_ms': hi})
    tdm = {'checkpoints': timed, 'completed_fps': None, 'completed_fps_bounds': None}
    if len(timed) >= 2 and all(b['completed'] >= a['completed'] for a, b in zip(timed, timed[1:])):
        first, last = timed[0], timed[-1]
        delta = last['completed'] - first['completed']
        shortest = (last['earliest_ms'] - first['latest_ms']) / 1000
        longest = (last['latest_ms'] - first['earliest_ms']) / 1000
        if shortest > 0 and longest >= shortest:
            tdm.update(completed_delta=delta, elapsed_seconds_bounds=[shortest, longest],
                       completed_fps_bounds=[delta / longest, delta / shortest])
    common_intervals = None
    for c in CAMERAS:
        intervals = [(r['started_ms'], r['ended_ms']) for r in camera_metrics[c]['windows'] if r['delivered_frames'] > 0]
        if common_intervals is None:
            common_intervals = intervals
        else:
            common_intervals = [(max(a, c0), min(b, d)) for a, b in common_intervals
                                for c0, d in intervals if max(a, c0) < min(b, d)]
    traffic_live = bool(common_intervals)
    sampled_live = all(camera_metrics[c]['sampled_delivered_fps_mean'] is not None and
                       camera_metrics[c]['sampled_delivered_fps_mean'] > 0 for c in CAMERAS)
    pane_live = any(v.get('mode') == '6' and v.get('have') == '111111' for v in panes)
    limits.extend(['Fresh paints are composite display updates, not summed camera FPS.',
                   'Capture DMA bytes and GPU uploads are logical payload; physical DDR bandwidth is unmeasured.',
                   'Sampled capture delivery rates lack exact window weights; expected baseline payload excludes retries, tag reads and other traffic.',
                   'Cumulative inference checkpoints give conservative rate bounds only; sampled one-second stats cannot establish actual interval inference FPS.'])
    return {'display': display, 'inference': infer, 'capture': camera_metrics, 'tdm': tdm,
            'all_six_live': traffic_live or (sampled_live and pane_live),
            'live_evidence': {'completed_delivery_windows': traffic_live, 'common_delivery_intervals_ms': common_intervals,
                              'sampled_delivery': sampled_live, 'six_panes': pane_live},
            'observation_seconds': observed_seconds, 'source_monotonic_bounds_seconds': [lower, upper] if bounded else None,
            'exclusions': exclusions, 'parse_errors': errors, 'limits': limits}


def compare(baseline_document, candidate_document):
    baseline, candidate = map(parse_observation, (baseline_document, candidate_document))

    def relation(base, value, smaller=False):
        if base is None or value is None or base <= 0:
            return {'status': 'unavailable', 'baseline': base, 'candidate': value}
        improved = value < base if smaller else value > base
        return {'status': 'improved' if improved else 'equal' if value == base else 'regressed',
                'baseline': base, 'candidate': value, 'ratio': value / base}

    fresh = relation(baseline['display']['fresh_paint_fps'], candidate['display']['fresh_paint_fps'])
    inference = relation(baseline['inference']['completed_fps'], candidate['inference']['completed_fps'])
    inference['baseline_checkpoint_fps_bounds'] = baseline['tdm']['completed_fps_bounds']
    if baseline['inference']['completed_fps'] is None:
        inference['reason'] = 'Baseline exact successful inference timing is missing; improvement is not established.'
        bounds = baseline['tdm']['completed_fps_bounds']
        value = candidate['inference']['completed_fps']
        inference['relation_to_baseline_checkpoint_bounds'] = (
            'unavailable' if bounds is None or value is None else
            'below' if value < bounds[0] else 'above' if value > bounds[1] else 'within')
    payload_by_camera = {}
    exact_payload = all(baseline['capture'][c]['dma_bytes_per_second'] is not None for c in CAMERAS)
    for c in CAMERAS:
        exact_camera = baseline['capture'][c]['dma_bytes_per_second'] is not None
        expected = baseline['capture'][c]['dma_bytes_per_second'] if exact_camera else baseline['capture'][c]['sampled_delivered_fps_mean']
        if not exact_camera:
            expected = expected * FRAME_PAYLOAD_BYTES if expected is not None else None
        r = relation(expected, candidate['capture'][c]['dma_bytes_per_second'], True)
        if not exact_camera:
            r['status'] = 'estimated_' + r['status'] if r['status'] != 'unavailable' else r['status']
            r['baseline_expected_frame_payload_bytes'] = FRAME_PAYLOAD_BYTES
        payload_by_camera[c] = r
    expected_total = sum(r['baseline'] for r in payload_by_camera.values()) if all(r['baseline'] is not None for r in payload_by_camera.values()) else None
    actual_total = sum(r['candidate'] for r in payload_by_camera.values()) if all(r['candidate'] is not None for r in payload_by_camera.values()) else None
    payload = relation(expected_total, actual_total, True)
    if not exact_payload:
        payload['status'] = 'estimated_' + payload['status'] if payload['status'] != 'unavailable' else payload['status']
    payload['per_camera'] = payload_by_camera
    payload['measurement'] = 'exact_logical_dma' if exact_payload else 'estimated_historical_frame_payload'
    payload['uncertainty'] = ('Both receipts use actual complete-window logical DMA byte counters; per-camera window durations can differ. Physical DDR bandwidth is unmeasured.' if exact_payload else
        'Baseline uses sampled delivered FPS after discarding its first sample, not measured DMA totals; candidate per-camera complete window durations differ. Small changes do not establish payload improvement beyond measurement uncertainty.')
    reasons = []
    for label, document, metrics in (('baseline', baseline_document, baseline), ('candidate', candidate_document, candidate)):
        reasons.extend(label + ': ' + reason for reason in _receipt_evidence(document))
        if metrics['inference']['window_count'] == 0 or not metrics['inference']['observation_failure_counts_complete']:
            reasons.append(label + ': Missing exact successful inference/failure totals')
        if metrics['inference']['observed_failed'] != 0:
            reasons.append(label + ': Exact inference failures must be zero')
        if metrics['display']['window_count'] == 0:
            reasons.append(label + ': Missing exact fresh display counts')
        if not metrics['live_evidence']['completed_delivery_windows']:
            reasons.append(label + ': Missing overlapping exact delivery windows for all six cameras')
        if any(not metrics['capture'][c]['window_count'] for c in CAMERAS):
            reasons.append(label + ': Missing exact six-camera DMA totals')
        if any(metrics['capture'][c]['read_errors'] for c in CAMERAS):
            reasons.append(label + ': Capture read errors must be zero')
        if metrics['parse_errors'] or any(e['reason'] not in {'Boundary-straddling window', 'Unbracketed boundary window'} for e in metrics['exclusions']):
            reasons.append(label + ': Malformed, missing, duplicate or unsupported exact evidence')
    bb, cb = baseline_document.get('binding', {}), candidate_document.get('binding', {})
    if not isinstance(bb, dict):
        bb = {}
    if not isinstance(cb, dict):
        cb = {}
    for key in ('host', 'config_sha256', 'baseline_sha256', 'settings_sha256'):
        if not bb.get(key) or bb.get(key) != cb.get(key):
            reasons.append('Stable configuration binding missing or changed: ' + key)
    bs, cs = baseline_document.get('spec', {}), candidate_document.get('spec', {})
    if not isinstance(bs, dict):
        bs = {}
    if not isinstance(cs, dict):
        cs = {}
    if not bs.get('assets') or bs.get('assets') != cs.get('assets'):
        reasons.append('Model asset pins missing or changed')
    bo, co = bs.get('overrides', {}), cs.get('overrides', {})
    if isinstance(bo, dict) and isinstance(co, dict):
        if any(bo.get(k) != co.get(k) for k in (set(bo) | set(co)) - INTENTIONAL_OVERRIDES):
            reasons.append('Environment changed outside intentional ring/capture pacing overrides')
        if (set(bo) | set(co)) - INTENTIONAL_OVERRIDES - {'DET_BENCH'}:
            reasons.append('Unsupported environment override evidence')
    established = not reasons and exact_payload
    improved = all(r['status'] == 'improved' for r in (fresh, inference, payload))
    accepted = improved if established else None
    return {'schema': 1, 'baseline': baseline, 'candidate': candidate,
            'comparison': {'fresh_video_fps': fresh, 'successful_inference_fps': inference,
                           'logical_capture_read_payload_bytes_per_second': payload,
                           'all_six_live': candidate['all_six_live'],
                            'accepted': accepted, 'acceptance_status': ('performance_improved' if accepted else 'performance_not_improved') if established else 'not_established',
                            'acceptance_reasons': reasons,
                            'acceptance_scope': 'Measured performance only; pixel parity, deployment and completion of all requirements are outside this audit.',
                            'physical_ddr_bandwidth': 'unmeasured'}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidates', nargs='+', type=Path)
    parser.add_argument('--baseline', type=Path, default=Path(__file__).parent / 'baseline/runtime_120s.json',
                        help='Historical segment JSON or successful instrumented original board_session observe receipt')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text(encoding='utf-8'))
    results = [{'candidate_receipt': str(path), **compare(baseline, json.loads(path.read_text(encoding='utf-8')))} for path in args.candidates]
    args.output.write_text(json.dumps({'baseline_path': str(args.baseline), 'results': results}, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps([{'candidate_receipt': r['candidate_receipt'], **r['comparison']} for r in results], indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
