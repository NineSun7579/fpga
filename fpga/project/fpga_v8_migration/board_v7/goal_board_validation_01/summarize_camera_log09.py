"""Summarize real viewer capture rates; positive rates alone are not visual acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def summarize(raw):
    rows = []
    pattern = rb'\[capture\] camera=(\d+) delivered_fps=([\d.]+) tag_advance_rate=([\d.]+) read_ms=([\d.]+) frame_dma_ms=([\d.]+) copy_ms=([\d.]+) unstable=(\d+)'
    for m in re.finditer(pattern, raw):
        rows.append({'camera': int(m[1]), 'delivered_fps': float(m[2]),
                     'tag_advance_rate': float(m[3]), 'read_ms': float(m[4]),
                     'frame_dma_ms': float(m[5]), 'copy_ms': float(m[6]),
                     'unstable': int(m[7]), 'byte_offset': m.start()})
    latest = {r['camera']: r for r in rows}
    missing = sorted(set(range(1, 7)) - set(latest))
    stalled = [c for c in range(1, 7) if c in latest and
               (latest[c]['delivered_fps'] <= 0 or latest[c]['tag_advance_rate'] <= 0)]
    errors = [{'byte_offset': m.start(), 'line': m[0].decode('utf-8', 'replace')}
              for m in re.finditer(rb'^.*(?:timeout|timed out|DMA.*fail|capture.*fail|NPU.*fail|segmentation fault).*$',
                                   raw, re.I | re.M)]
    inference = []
    for m in re.finditer(rb'^\[stats\][^\r\n]*$', raw, re.M):
        values = {name.decode('ascii'): float(value) for name, value in
                  re.findall(rb'([a-z_]+)=(-?\d+(?:\.\d+)?)', m[0])}
        required = {'npu_request_fps', 'npu_started_fps', 'npu_completed_fps', 'npu_failed_fps'}
        if required <= values.keys():
            inference.append({'byte_offset': m.start(), **values})
    latest_inference = inference[-1] if inference else None
    return {'capture_rows': rows, 'latest_per_camera': latest, 'missing_cameras': missing,
            'stalled_cameras': stalled, 'error_candidates': errors,
            'positive_capture_rates_all_six': not missing and not stalled,
            'inference_rows': inference, 'latest_inference': latest_inference,
            'inference_completion_observed': bool(latest_inference and
                latest_inference['npu_completed_fps'] > 0),
            'inference_failure_observed': any(row['npu_failed_fps'] > 0 for row in inference),
            'video_log_present': b'[video]' in raw,
            'functional_pass': False,
            'remaining_review': 'Bind to actual boot/program/viewer; compare two captures and inspect images, RAW/model and motion results. Rates do not prove frame content.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--log', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    raw = a.log.read_bytes()
    result = summarize(raw)
    result['log'] = {'path': str(a.log.resolve()), 'bytes': len(raw),
                     'sha256': hashlib.sha256(raw).hexdigest()}
    with a.output.open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    print(json.dumps({'positive_capture_rates_all_six': result['positive_capture_rates_all_six'],
                      'missing_cameras': result['missing_cameras'],
                      'stalled_cameras': result['stalled_cameras'],
                      'error_candidates': len(result['error_candidates']),
                      'functional_pass': False}))


if __name__ == '__main__':
    main()
