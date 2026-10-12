from pathlib import Path
import argparse
import json
import re
import statistics

parser = argparse.ArgumentParser()
parser.add_argument('--six-camera', action='store_true')
parser.add_argument('--batch', action='store_true')
parser.add_argument('--async-candidate', action='store_true')
parser.add_argument('--background-candidate', action='store_true')
args = parser.parse_args()
root = Path(__file__).resolve().parent
folder = root / ('six_async_display_measurement' if args.async_candidate else 'six_batch_display_measurement' if args.batch else 'six_display_measurement' if args.six_camera else 'display_measurement')
if args.background_candidate: folder = root / 'six_background_display_measurement'
arms = json.loads((folder / 'arms.json').read_text())
records = []
for index, arm in enumerate(arms):
    label = str(index + 1) + arm['arm']
    host = json.loads((folder / (label + '_host.json')).read_text())
    text = (folder / (label + '.log')).read_text(errors='replace')
    end = host['samples'][-1]['time']
    start = end - host['wall_seconds']
    inference = [(float(stamp), float(latency)) for stamp, latency in
        re.findall(r'\[tdm_bench\] t=([\d.]+) model=\S+ ms=([\d.]+)', text)]
    inference = [latency for stamp, latency in inference if start <= stamp <= end]
    capture = {}
    for camera, rate in re.findall(r'\[capture\] camera=(\d+) delivered_fps=([\d.]+)', text):
        capture.setdefault(camera, []).append(float(rate))
    submits = [float(rate) for rate in re.findall(r'\[panes\].*?submit_fps=([\d.]+)', text)]
    uploads = {}
    for camera, count, size in re.findall(r'\[display-upload\] camera=(\d+) count=(\d+) bytes=(\d+)', text):
        previous = uploads.setdefault(camera, {'frames': 0, 'bytes': 0})
        previous['frames'] += int(count)
        previous['bytes'] += int(size)
    records.append({**arm, 'label': label,
        'rknn_completions_in_sample': len(inference),
        'rknn_completions_per_second': len(inference) / host['wall_seconds'],
        'rknn_mean_ms': statistics.mean(inference) if inference else None,
        'logged_capture_fps': {camera: statistics.mean(values) for camera, values in capture.items()},
        'logged_submit_fps': statistics.mean(submits) if submits else None,
        'logged_gl_uploads': uploads,
        'thumbnail_format_observed': 'width=320 height=240 bytes=153600 thumbnail=1' in text})
groups = {}
for arm in ('A', 'B'):
    rows = [row for row in records if row['arm'] == arm]
    if rows:
        groups[arm] = {field: statistics.mean(row[field] for row in rows) for field in
            ('cpu_percent_one_core', 'peak_rss_kib', 'rknn_completions_per_second')}
report = {'runs': records, 'means': groups,
    'limits': 'Capture/submit FPS are log-window means including warmup. RKNN completion rate uses host monotonic sample window. Submit FPS is not fresh/optical display FPS. DMA byte reduction and optical latency are not measured.'}
if (folder/'scope.json').exists():
    report['acceptance_scope']=json.loads((folder/'scope.json').read_text())
report['complete_requested_run']=not (folder/'failure.txt').exists() and (folder/'restored_pid.txt').exists()
requested=report.get('acceptance_scope',{}).get('requested_arms')
if requested:
    report['complete_requested_run']=report['complete_requested_run'] and ''.join(row['arm'] for row in records)==requested
if set(groups) == {'A', 'B'}:
    report['cpu_reduction_percent'] = 100 * (1 - groups['B']['cpu_percent_one_core'] / groups['A']['cpu_percent_one_core'])
(folder / 'summary.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
