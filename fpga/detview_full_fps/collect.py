import argparse
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import board_ssh

parser = argparse.ArgumentParser()
parser.add_argument('--log', default='/userdata/linaro/detview_full_cam5_fps.log')
parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent)
parser.add_argument('--no-shot', action='store_true')
parser.add_argument('--windows', type=int, help='Use the first N complete windows after startup')
args = parser.parse_args()
dest = args.output.resolve()
dest.mkdir(parents=True, exist_ok=True)
client = board_ssh.connect()
try:
    rc, log, err = board_ssh.run(client, 'cat ' + args.log, sudo=True)
    if rc:
        raise RuntimeError(err)
    (dest / 'detview_full_cam5_fps.log').write_text(log, encoding='utf-8')
    windows = []
    current = None
    for line in log.splitlines():
        if line.startswith('[display-perf]'):
            current = {k: float(v) for k, v in re.findall(r'(seconds|swap_fps|upload_fps|new_paint_fps)=([\d.]+)', line)}
            current['cameras'] = {}
            windows.append(current)
        elif line.startswith('[display-upload]') and current:
            match = re.search(r'camera=(\d+) count=(\d+)', line)
            if match:
                current['cameras'][match[1]] = int(match[2]) / current['seconds']
    windows = [w for w in windows[1:] if len(w['cameras']) == 6]
    if args.windows:
        if len(windows) < args.windows:
            raise RuntimeError(f'Need {args.windows} windows, have {len(windows)}')
        windows = windows[:args.windows]
    seconds = sum(w['seconds'] for w in windows)
    result = {'model': 'MVP_accuracy_round1', 'measurement_seconds': seconds, 'windows': len(windows), 'cameras': {}}
    for cam in range(1, 7):
        captures = [float(v) for k, v in re.findall(r'\[capture\] camera=(\d+) delivered_fps=([\d.]+)', log) if int(k) == cam][1:len(windows) + 1]
        uploads = [w['cameras'][str(cam)] for w in windows]
        result['cameras'][str(cam)] = {'capture_fps_mean': statistics.mean(captures), 'display_fps_mean': sum(w['cameras'][str(cam)] * w['seconds'] for w in windows) / seconds, 'display_fps_min': min(uploads), 'display_fps_max': max(uploads)}
    result['swap_fps_mean'] = sum(w['swap_fps'] * w['seconds'] for w in windows) / seconds
    result['swap_fps_min'] = min(w['swap_fps'] for w in windows)
    result['swap_fps_max'] = max(w['swap_fps'] for w in windows)
    infer = [float(v) for v in re.findall(r'npu_completed_fps=([\d.]+)', log)][1:len(windows) + 1]
    result['inference_fps_mean'] = statistics.mean(infer)
    failed = [float(v) for v in re.findall(r'npu_failed_fps=([\d.]+)', log)]
    result['inference_failed_fps_max'] = max(failed) if failed else None
    result['display_config'] = re.findall(r'\[display-config\].*', log)
    result['runtime_faults'] = re.findall(r'^.*(?:\[recover\]|decode_ok=0|RKNN_ERR|Segmentation fault).*$', log, re.M)
    result['unstable_nonzero'] = len(re.findall(r'unstable=[1-9]\d*', log))
    result['panes_error_nonzero'] = [v for v in re.findall(r'err=([\d/]+)', log) if any(int(x) for x in v.split('/'))]
    rc, load, err = board_ssh.run(client, 'cat /sys/kernel/debug/rknpu/load', sudo=True)
    result['npu_load_snapshot'] = load.strip()
    if not args.no_shot:
        sftp = client.open_sftp()
        shots = [f for f in sftp.listdir_attr('/userdata/detview_shots') if f.filename.startswith('shot_MVP_accuracy_round1')]
        latest = max(shots, key=lambda f: f.st_mtime)
        sftp.get('/userdata/detview_shots/' + latest.filename, str(dest / 'detview_full.png'))
        result['screenshot_source'] = latest.filename
        sftp.close()
    (dest / 'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
finally:
    client.close()
