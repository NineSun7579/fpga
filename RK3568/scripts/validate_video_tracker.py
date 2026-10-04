#!/usr/bin/env python3
"""Board-only video-input tracker validation, leave detview running for review."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.path.append('/userdata/linaro/detview-todo-work')
import validate_detview_live as live

WORK = Path('/userdata/linaro/detview-video-work')
OUT = WORK / 'validation'
VIDEO = WORK / 'media/VID_20260912_151339_480p30.mp4'
MODEL = '/root/npu/yolov8n/zebra640/det-yolov8n-zebra-merged-v3-rk3568-raw-dfl6-int8.rknn'


def holders():
    r = subprocess.run(['fuser', '/dev/pango_pci_driver'], capture_output=True, text=True)
    if r.returncode not in (0, 1):
        raise RuntimeError('Cannot verify PCIe ownership')
    return [int(v) for v in r.stdout.split() if v.isdigit()]


def shot(name):
    subprocess.run(['/root/ov5640/qshot/qshot', str(OUT / (name + '.png')), '1920'],
                   env=live.ENV, capture_output=True, check=True, timeout=15)


def watch(proc, seconds, name):
    start = time.monotonic()
    with (OUT / (name + '.jsonl')).open('w') as out:
        while time.monotonic() - start < seconds:
            if proc.poll() is not None:
                raise RuntimeError(f'Video viewer exited {proc.returncode}')
            row = live.sample(proc.pid, name)
            child_pids = set()
            child_files = list(Path(f'/proc/{proc.pid}/task').glob('*/children'))
            for path in child_files:
                try:
                    child_pids.update(int(v) for v in path.read_text().split())
                except FileNotFoundError:
                    continue
            if not child_files:
                # Some board kernels omit CONFIG_PROC_CHILDREN.
                for process_path in Path('/proc').iterdir():
                    if not process_path.name.isdigit():
                        continue
                    try:
                        parent = re.search(r'^PPid:\s*(\d+)', (process_path / 'status').read_text(), re.M)
                        if parent and int(parent[1]) == proc.pid:
                            child_pids.add(int(process_path.name))
                    except (FileNotFoundError, PermissionError):
                        continue
            children = []
            for pid in sorted(child_pids):
                try:
                    child = live.sample(pid, name)
                    children.append({'pid': pid, 'cpu_seconds': child['cpu_seconds'], 'rss_kib': child['rss_kib']})
                except FileNotFoundError:
                    continue
            row['children'] = children
            row['decoder_cpu_seconds'] = sum(v['cpu_seconds'] for v in children)
            row['decoder_rss_kib'] = sum(v['rss_kib'] for v in children)
            out.write(json.dumps(row) + '\n')
            out.flush()
            time.sleep(min(1, max(0, seconds - (time.monotonic() - start))))
    (OUT / (name + '.window.json')).write_text(json.dumps({'started_ms': start * 1000,
                                                         'ended_ms': time.monotonic() * 1000}))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if not VIDEO.is_file() or not Path(MODEL).is_file():
        raise RuntimeError('Video/model missing')
    active = OUT / 'active.json'
    if active.is_file():
        old = json.loads(active.read_text())
        proc = Path(f"/proc/{old['pid']}")
        if proc.exists() and live.alive(old['pid']):
            actual = (proc / 'cmdline').read_bytes().decode().split('\0')[:-1]
            exe = os.readlink(proc / 'exe').removesuffix(' (deleted)')
            if actual != old['args'] or exe != str(WORK / 'build/detview'):
                raise RuntimeError('Previous video PID identity changed')
            live.quit_viewer(old['pid'])
    owned = holders()
    if len(owned) > 1:
        raise RuntimeError('Multiple viewers occupy device')
    for pid in owned:
        proc = Path(f'/proc/{pid}')
        exe = os.readlink(proc / 'exe').removesuffix(' (deleted)')
        if not exe.endswith('/detview') and not exe.endswith('/camview'):
            raise RuntimeError('Unexpected camera-device owner')
        old = {'pid': pid, 'exe': exe, 'cwd': os.readlink(proc / 'cwd'),
               'args': (proc / 'cmdline').read_bytes().decode().split('\0')[:-1]}
        (OUT / 'previous-viewer.json').write_text(json.dumps(old, indent=2))
        live.quit_viewer(pid)
    if holders():
        raise RuntimeError('PCIe remains occupied')
    env = dict(live.ENV, DETVIEW_SWAP_INTERVAL='0', DETVIEW_TEXTURE_RING='1', DETVIEW_VIDEO_FPS='30', DETVIEW_PERF='1')
    for k in ('DETVIEW_STEREO_TRIAL_METERS', 'DETVIEW_STEREO_VEHICLE_TRIAL', 'DETVIEW_CALIBRATION_CAPTURE'):
        env.pop(k, None)
    args = [str(WORK / 'build/detview'), '--video', str(VIDEO), '--video-loop',
            '--model', MODEL, '--fullscreen', '--tracker-debug',
            '--detect-interval-ms', '250', '--detect-min-ms', '250',
            '--track-interval-ms', '33', '--track-template-side', '48', '--max-tracks', '12']
    with (OUT / 'detview.log').open('w') as log:
        p = subprocess.Popen(args, cwd=WORK / 'build', env=env, stdout=log, stderr=log, start_new_session=True)
    (OUT / 'active.json').write_text(json.dumps({'pid': p.pid, 'args': args, 'source_resolution': '640x480',
                                              'video_fps': 30, 'vehicle_only_tracking': True}, indent=2))
    print('VIDEO_TRACKER_STARTED', p.pid, flush=True)
    watch(p, 10, 'warmup')
    shot('monitor-10s')
    watch(p, 60, 'sample')
    shot('monitor-70s')
    live.key(p.pid, 'p')
    watch(p, 3, 'paused'); shot('paused')
    live.key(p.pid, 'p')
    watch(p, 5, 'resumed'); shot('resumed')
    live.key(p.pid, 'Tab')
    watch(p, 2, 'settings'); shot('settings')
    live.key(p.pid, 'Escape')
    # Playback runs beyond the 80.3s source duration to check the loop seam.
    watch(p, 20, 'loop-check'); shot('loop-monitor')
    text = (OUT / 'detview.log').read_text(errors='replace')
    debug = [json.loads(line.split('] ', 1)[1]) for line in text.splitlines() if line.startswith('[tracker-debug]')]
    if not debug or not any(r['tracked_vehicles'] > 0 for r in debug):
        raise RuntimeError('No tracked vehicles published')
    for row in debug:
        for box in row['boxes']:
            if box['id'] != '0' and box['class'] != 1:
                raise RuntimeError('Nonvehicle entered template tracking')
    info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                      '-show_entries', 'stream=nb_frames', '-of', 'json', str(VIDEO)], text=True))
    frames = int(info['streams'][0]['nb_frames'])
    audits = [dict(re.findall(r'(\w+)=([^\s]+)', line)) for line in text.splitlines()
              if line.startswith('[video]') and 'source_index=' in line and 'capture_fps=' in line]
    paused = json.loads((OUT / 'paused.window.json').read_text())
    if any(paused['started_ms'] + 250 < float(row['captured_ms']) < paused['ended_ms'] for row in audits):
        raise RuntimeError('Video captured frames while paused')
    resumed = json.loads((OUT / 'resumed.window.json').read_text())
    resume_rows = [row for row in audits if resumed['started_ms'] <= float(row['captured_ms']) <= resumed['ended_ms']]
    if len(resume_rows) < 2 or any(float(row['capture_fps']) > 31 for row in resume_rows):
        raise RuntimeError('Resume stalled or exceeded configured playback rate')
    after_loop = [row for row in audits if int(row['source_index']) > frames]
    if len(after_loop) < 3 or int(after_loop[-1]['sequence']) <= int(after_loop[0]['sequence']):
        raise RuntimeError('No evidence of continuous frames beyond loop seam')
    if not any(int(row['source_frame']) > frames for row in debug):
        raise RuntimeError('No tracker update after loop seam')
    (OUT / 'checks.json').write_text(json.dumps({'vehicle_only': True, 'loop_frames': frames,
        'last_source_index': int(audits[-1]['source_index']), 'after_loop_audits': len(after_loop),
        'last_capture_fps': float(audits[-1]['capture_fps']), 'pause_stopped_frames': True,
        'resume_capture_fps': [float(row['capture_fps']) for row in resume_rows]}, indent=2))
    if re.search(r'shader.*failed|QOpenGLShader.*error|FATAL', text, re.I):
        raise RuntimeError('Video/GL error in log')
    if holders() and p.pid in holders():
        raise RuntimeError('Video viewer unexpectedly opened PCIe')
    print('VIDEO_TRACKER_UI_PASS', p.pid, flush=True)
    print('VIDEO_LEFT_RUNNING', p.pid, flush=True)


if __name__ == '__main__':
    main()
