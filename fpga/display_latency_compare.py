"""Compare software display-age windows; does not measure optical latency."""
import argparse
import json
import re
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('logs', nargs='+', type=Path)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
report = {'scope': 'software timestamps only; no exposure, panel scanout or pixel response measurement', 'runs': []}
for path in args.logs:
    text = path.read_text(encoding='utf-8', errors='replace')
    stages = {}
    camera_stages = {}
    for line in text.splitlines():
        if '[display-stage]' not in line and '[display-latency]' not in line:
            continue
        fields = dict(re.findall(r'(\w+)=([^\s]+)', line))
        if '[display-latency]' in line:
            key = fields['camera'] + ':' + fields['stage']
            camera_stages.setdefault(key, []).append({name: float(fields[name]) for name in
                ('count', 'sum_ms', 'p50_le_ms', 'p95_le_ms', 'max_ms', 'refreshed')})
            continue
        name = fields['name']
        entries = stages.setdefault(name, [])
        entries.append({key: float(fields[key]) for key in ('count', 'sum_ms', 'p50_le_ms', 'p95_le_ms', 'max_ms')})
    # Exclude startup windows; use the same number in each run.
    summaries = {}
    for name, windows in stages.items():
        selected = windows[2:14]
        count = sum(row['count'] for row in selected)
        summaries[name] = {'windows': len(selected), 'count': count,
                           'mean_ms': sum(row['sum_ms'] for row in selected) / count if count else None,
                           'window_p95_max_ms': max((row['p95_le_ms'] for row in selected), default=None),
                           'max_ms': max((row['max_ms'] for row in selected), default=None)}
    faults = [line for line in text.splitlines() if re.search(r'FATAL|decode_ok=0|unstable=[1-9]|err=(?!0/0/0/0/0/0)', line)]
    camera_summaries = {}
    for name, windows in camera_stages.items():
        selected = windows[2:14]
        count = sum(row['count'] for row in selected)
        camera_summaries[name] = {'windows': len(selected), 'count': count,
            'sum_ms': sum(row['sum_ms'] for row in selected),
            'mean_ms': sum(row['sum_ms'] for row in selected) / count if count else None,
            'window_p95_max_ms': max((row['p95_le_ms'] for row in selected), default=None),
            'max_ms': max((row['max_ms'] for row in selected), default=None),
            'refreshed': sum(row['refreshed'] for row in selected)}
    mode = re.search(r'\[display-latency\] late_latch=(\d)', text)
    report['runs'].append({'log': str(path), 'late_latch': int(mode.group(1)) if mode else None,
                          'stages': summaries, 'cameras': camera_summaries, 'faults': faults})
comparison = {}
for mode in (0, 1):
    runs = [run for run in report['runs'] if run['late_latch'] == mode]
    groups = {}
    for run in runs:
        for name, values in run['cameras'].items():
            group = groups.setdefault(name, {'count': 0, 'sum_ms': 0})
            group['count'] += values['count']
            group['sum_ms'] += values['sum_ms']
    for group in groups.values():
        group['mean_ms'] = group['sum_ms'] / group['count'] if group['count'] else None
    comparison[str(mode)] = groups
report['pooled_modes'] = comparison
report['mean_reduction_ms'] = {name: comparison['0'][name]['mean_ms'] - values['mean_ms']
    for name, values in comparison['1'].items() if name in comparison['0'] and values['count'] and comparison['0'][name]['count']}
args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
