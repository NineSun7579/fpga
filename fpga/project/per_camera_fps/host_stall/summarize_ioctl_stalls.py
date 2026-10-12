"""Offline attempt accounting. Slow-only logs cannot provide all-attempt means."""
import argparse
import hashlib
import json
import re
from pathlib import Path

DIAG = re.compile(r'\[diag\]\s+t=(?P<t>[\d.]+)\s+pango_ioctl\s+cmd=(?P<cmd>[0-9a-fA-F]+)\s+addr=(?P<addr>0x[0-9a-fA-F]+)\s+len=(?P<size>\d+)\s+ms=(?P<ms>[\d.]+)\s+rc=(?P<rc>-?\d+)\s+errno=(?P<errno>\d+)\s+alarm=(?P<alarm>\d+)')
KV = re.compile(r'(\w+)=([^\s]+)')
STEREO_WINDOW = re.compile(r'window=\[(\d+),(\d+)\)')
BASES = [(0x800000, 0xa00000), (0xc00000, 0xe00000),
         (0x1000000, 0x1200000), (0x1400000, 0x1600000),
         (0x1800000, 0x1a00000), (0x1c00000, 0x1e00000)]

def camera_address(address):
    for camera, banks in enumerate(BASES, 1):
        for bank, base in enumerate(banks):
            if base <= address < base + 614416:
                return camera, bank, address - base
    return None, None, None

def overlap_bounds(start, end, duration, completion_low, completion_high):
    """Possible interval overlaps; completion bins are not exact timestamps."""
    def overlap(completion):
        return max(0, min(end, completion) - max(start, completion-duration))
    endpoints = [completion_low, completion_high]
    candidates = endpoints + [max(completion_low, min(completion_high, point))
                              for point in (end, start+duration)]
    return {'minimum_ms': min(map(overlap, endpoints)),
            'maximum_ms': max(map(overlap, candidates))}

def summarize_text(text, name, long_ms=1000):
    attempts, windows, captures, stereo = [], [], [], []
    window = None
    for number, line in enumerate(text.splitlines(), 1):
        fields = dict(KV.findall(line))
        if line.startswith('[display-perf]'):
            window = {'line': number, 'start_ms': int(fields['started_ms']),
                      'end_ms': int(fields['ended_ms']), 'stages': {}}
            windows.append(window)
        elif line.startswith('[display-stage]') and window is not None:
            window['stages'][fields['name']] = {'line': number, 'count': int(fields['count']),
                'sum_ms': float(fields['sum_ms']), 'max_ms': float(fields['max_ms'])}
        elif line.startswith('[capture]'):
            captures.append({'line': number, 'camera': int(fields['camera']),
                             'raw': line, 'fields': fields})
        elif line.startswith('[stereo]'):
            bounds = STEREO_WINDOW.search(line)
            if bounds:
                stereo.append({'line': number, 'raw': line, 'fields': fields,
                    'completion_window_start_ms': int(bounds[1]),
                    'completion_window_end_ms': int(bounds[2]),
                    'compute_max_ms': float(fields['compute_max_ms'])})
        match = DIAG.search(line)
        if not match:
            continue
        f = match.groupdict()
        elapsed, end = float(f['ms']), float(f['t']) * 1000
        rc, alarm = int(f['rc']), int(f['alarm'])
        camera, bank, offset = camera_address(int(f['addr'], 16))
        inferred_rx = None
        if camera is not None and f['cmd'].lower()=='c0045305':
            if offset == 614400 and int(f['size'])==16:
                inferred_rx = '0x003ff000'
            elif offset == 0 and int(f['size'])==614416:
                inferred_rx = f'0x{(camera-1)*0x97000:08x}'
        # Classification is explicitly the retained calibration control flow.
        failed = rc < 0 or alarm != 0
        attempts.append({'line': number, 'raw': line, 'completion_monotonic_s': f['t'],
            'start_estimate_monotonic_ms': end - elapsed, 'end_monotonic_ms': end,
            'timestamp_resolution_ms': 1, 'elapsed_ms': elapsed, 'cmd': f['cmd'],
            'requested_ddr_address': f['addr'], 'requested_bytes': int(f['size']),
            'camera_from_address': camera, 'bank': bank, 'offset_from_camera_bank': offset,
            'rx_offset': None, 'tid': None, 'retry_id': None,
            'rx_offset_under_retained_source': inferred_rx,
            'rc': rc, 'errno_raw': int(f['errno']), 'errno_valid': rc < 0,
            'alarm': alarm, 'application_failure_under_retained_source': failed,
            'long': elapsed >= long_ms})
    for index, attempt in enumerate(attempts):
        previous = attempts[index-1] if index else None
        attempt['gap_from_previous_logged_completion_ms'] = (
            attempt['start_estimate_monotonic_ms'] - previous['end_monotonic_ms'] if previous else None)
        # A stage window supplies aggregates, not exact event start/end timestamps.
        candidates = [w for w in windows if w['start_ms']-20 <= attempt['end_monotonic_ms'] <= w['end_ms']+20]
        selected = min(candidates, key=lambda w: abs(w['end_ms']-attempt['end_monotonic_ms'])) if candidates else None
        attempt['display_window'] = selected
        attempt['gui_delay_overlap_bounds_under_retained_source'] = (
            overlap_bounds(attempt['start_estimate_monotonic_ms'], attempt['end_monotonic_ms'],
                           selected['stages']['gui_delay']['max_ms'],
                           selected['start_ms'], selected['end_ms'])
            if selected and 'gui_delay' in selected['stages'] else None)
        attempt['stereo_max_interval_candidates_under_retained_source'] = []
        for report in stereo:
            if report['compute_max_ms'] <= 0:
                continue
            bounds = overlap_bounds(attempt['start_estimate_monotonic_ms'], attempt['end_monotonic_ms'],
                                    report['compute_max_ms'], report['completion_window_start_ms'],
                                    report['completion_window_end_ms'])
            if bounds['maximum_ms'] > 0:
                attempt['stereo_max_interval_candidates_under_retained_source'].append(
                    {**report, 'overlap_bounds': bounds})
        attempt['nearby_capture_reports'] = sorted(captures, key=lambda c: abs(c['line']-attempt['line']))[:6]
    failures = [a for a in attempts if a['application_failure_under_retained_source']]
    successes = [a for a in attempts if not a['application_failure_under_retained_source']]
    per_camera = {}
    for camera in range(1, 7):
        subset = [a for a in attempts if a['camera_from_address']==camera]
        bad = [a for a in subset if a['application_failure_under_retained_source']]
        reports = [c for c in captures if c['camera']==camera]
        per_camera[str(camera)] = {'logged_attempt_count': len(subset), 'logged_failure_count': len(bad),
            'logged_failure_elapsed_ms': sum(a['elapsed_ms'] for a in bad),
            'capture_report_count': len(reports),
            'successful_frame_dma_report_min_ms': min((float(c['fields']['frame_dma_ms']) for c in reports), default=None),
            'successful_frame_dma_report_max_ms': max((float(c['fields']['frame_dma_ms']) for c in reports), default=None),
            'weighted_success_mean_ms': None, 'true_all_attempt_mean_ms': None}
    return {'file': name, 'attempts': attempts, 'summary': {
        'logged_attempt_count': len(attempts), 'logged_failure_count': len(failures),
        'logged_success_count': len(successes), 'long_attempt_count': sum(a['long'] for a in attempts),
        'logged_alarm_nonzero_count': sum(a['alarm'] != 0 for a in attempts),
        'logged_negative_rc_count': sum(a['rc'] < 0 for a in attempts),
        'logged_failure_elapsed_ms': sum(a['elapsed_ms'] for a in failures),
        'logged_success_elapsed_ms': sum(a['elapsed_ms'] for a in successes),
        'per_camera': per_camera}, 'stereo_reports': stereo, 'limitations': [
        'Diagnostics emit only ms>=30 in retained source: counts and sums are observed lower bounds.',
        'No TID, RX offset, retry identifier, audit frame count or capture window bounds in these raw records.',
        'rc=0 errno is stale/unspecified; alarm=1 is application failure under retained source.',
        'Intervals are elapsed wall time, not exclusive kernel CPU or DMA hardware time.',
        'Capture means lack sample counts; weighted successful/all-attempt means cannot be recovered.',
        'Multiple log files may overlap; totals must not be summed across files without a byte-range receipt.',
        'Display window association uses completion time with 20ms boundary tolerance; not causal proof.',
        'GUI max endpoints are unknown: published time may precede the reporting window; similar durations alone do not prove overlap.',
        'Stereo overlap bounds assume retained vision_pipeline.cpp completion-window attribution, not yet verified in binary; bins do not give exact event times.',
        'Overlap bounds use printed times without expanding their approximately 1ms quantization uncertainty.']}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('logs', nargs='+', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--long-ms', type=float, default=1000)
    args = parser.parse_args()
    results = []
    for path in args.logs:
        raw = path.read_bytes()
        if path.suffix == '.json':
            record = json.loads(raw.decode('utf-8'))
            # Diagnosis owns a full old calibration log: prefer it to its duplicate tails.
            text = record.get('full_recovery_log')
            if isinstance(text, str) and DIAG.search(text):
                result = summarize_text(text, str(path)+':full_recovery_log', args.long_ms)
                result['sha256'] = hashlib.sha256(text.encode('utf-8')).hexdigest()
                result['embedded_log'] = {'container': str(path), 'field': 'full_recovery_log',
                    'viewer_identity': record.get('viewers'),
                    'warning': 'Overlaps recovery_observation.log; do not sum these streams.'}
                results.append(result)
            continue
        if path.suffix == '.jsonl':
            for record_number, line in enumerate(raw.decode('utf-8').splitlines(), 1):
                record = json.loads(line)
                for field in ('initial_log_tail', 'log_new'):
                    for remote_log, text in record.get(field, {}).items():
                        if not isinstance(text, str) or not DIAG.search(text):
                            continue
                        result = summarize_text(text, str(path)+f':{record_number}:{field}:{remote_log}', args.long_ms)
                        result['sha256'] = hashlib.sha256(text.encode('utf-8')).hexdigest()
                        result['embedded_log'] = {'container': str(path), 'record': record_number,
                            'field': field, 'remote_log': remote_log,
                            'sampling_identity': record.get('identity'),
                            'warning': 'Header sampler identity is not proof of ownership of historical log tails; no byte offset receipt.'}
                        results.append(result)
            continue
        result = summarize_text(raw.decode('utf-8', errors='replace'), str(path), args.long_ms)
        result['sha256'] = hashlib.sha256(raw).hexdigest()
        result['bytes'] = len(raw)
        receipt = path.with_name(path.name.replace('_observation.log', '_observe.json'))
        if receipt.suffix == '.json' and receipt.exists():
            events = json.loads(receipt.read_text(encoding='utf-8')).get('events', [])
            start = next((e for e in events if e.get('state')=='observation_started'), None)
            end = next((e for e in events if e.get('state')=='observed'), None)
            if start and end:
                lower, upper = start['monotonic']*1000, end['monotonic']*1000
                clipped = sum(max(0, min(a['end_monotonic_ms'], upper) -
                                  max(a['start_estimate_monotonic_ms'], lower))
                              for a in result['attempts'] if a['application_failure_under_retained_source'])
                result['observation_receipt'] = {'file': str(receipt), 'start_ms': lower,
                    'end_ms': upper, 'seconds': end.get('seconds'), 'byte_offset': start.get('offset'),
                    'byte_length': end.get('bytes'), 'remote_log': start.get('log'),
                    'clipped_logged_failure_elapsed_ms': clipped,
                    'clipped_failure_fraction_of_observed_wall': clipped/(upper-lower)}
                progress = [{'event_index': i, 'monotonic_ms': e['monotonic']*1000}
                            for i, e in enumerate(events) if e.get('state') == 'observation_progress']
                result['observation_receipt']['progress'] = progress
                for attempt in result['attempts']:
                    attempt['observer_progress_inside_interval'] = [e for e in progress
                        if attempt['start_estimate_monotonic_ms'] < e['monotonic_ms'] < attempt['end_monotonic_ms']]
        results.append(result)
    args.output.write_text(json.dumps({'logs': results}, indent=2), encoding='utf-8')
    print(json.dumps([{ 'file': r['file'], **{k:v for k,v in r['summary'].items() if k!='per_camera'}} for r in results], indent=2))

if __name__ == '__main__':
    main()
