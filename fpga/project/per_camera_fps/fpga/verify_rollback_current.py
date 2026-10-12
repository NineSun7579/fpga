"""Read-only identity-bound screenshot and retained rollback metrics."""
import argparse
import base64
import json
from pathlib import Path
import re
import statistics
import struct
from PIL import Image
import rollback_current as rollback

motion = rollback.motion

def health_summary(text, observation):
    rows = {}
    for line in text.splitlines():
        if line.startswith('[capture]'):
            values = dict(re.findall(r'(\w+)=([^\s]+)', line))
            rows.setdefault(values['camera'], []).append(values)
    cameras = {}
    for camera, values in rows.items():
        rates = [float(v['delivered_fps']) for v in values]
        tags = [float(v['tag_advance_rate']) for v in values]
        cameras[camera] = dict(samples=len(values), mean_delivered_fps=statistics.mean(rates),
            min_delivered_fps=min(rates), mean_tag_advance_rate=statistics.mean(tags),
            max_unstable=max(int(v['unstable']) for v in values))
    panes = re.findall(r'\[panes\].*have=([01]+).*err=([0-9/]+)', text)
    stats = [dict(re.findall(r'(\w+)=([^\s]+)', line)) for line in text.splitlines() if line.startswith('[stats]')]
    stereo = [dict(re.findall(r'(\w+)=([^\s]+)', line)) for line in text.splitlines() if line.startswith('[stereo]')]
    tdm = [int(v) for v in re.findall(r'\[tdm\].*completed=(\d+)', text)]
    error_lines = [line for line in text.splitlines() if re.search(r'\b(?:error|timeout)\b|EGL_BAD|failed=[1-9]|read_errors=[1-9]', line, re.I)]
    healthy = (observation['seconds'] >= 120 and set(cameras) == set('123456') and
        all(v['min_delivered_fps'] > 0 and v['mean_tag_advance_rate'] > 0 and v['max_unstable'] == 0 for v in cameras.values()) and
        bool(panes) and all(have == '111111' and all(int(v) == 0 for v in err.split('/')) for have,err in panes) and
        len(tdm) > 1 and tdm[-1] > tdm[0] and bool(stats) and
        all(float(v['npu_failed_fps']) == 0 for v in stats) and bool(stereo) and
        all(int(v['pair_compute_ok']) > 0 and int(v['pair_compute_failed']) == 0 for v in stereo) and not error_lines)
    return dict(recovery_healthy=healthy, observed_seconds=observation['seconds'], cameras=cameras,
        panes_samples=len(panes), inference_completed_first=tdm[0] if tdm else None,
        inference_completed_last=tdm[-1] if tdm else None,
        inference_completed_fps_range=[min(float(v['npu_completed_fps']) for v in stats),max(float(v['npu_completed_fps']) for v in stats)] if stats else None,
        stereo_successes=sum(int(v['pair_compute_ok']) for v in stereo),
        stereo_failures=sum(int(v['pair_compute_failed']) for v in stereo), error_lines=error_lines,
        limit='Capture rates are arithmetic means of reported intervals, not weighted FPS. This verifies recovery; it does not establish the original 40/30 optimization targets.')
EXTRA = r'''
prior_screenshot_action = action
def action(request, emit):
    if request['action'] != 'rollback_screenshot':
        return prior_screenshot_action(request, emit)
    import base64
    require(sha(request['snapshot']) == request['snapshot_sha256'], 'Snapshot hash changed')
    saved = private_read(request['snapshot'])
    require(saved['operation'] == request['start_operation'] and saved['boot_id'] == boot(), 'Snapshot identity mismatch')
    common = dict(config=saved['config'], baseline=saved['baseline'], target=request['target'])
    exact(common)
    verify_files(saved['config'], saved['baseline'])
    require(owners() == [request['target']['pid']], 'Owner changed before screenshot')
    win = windows(request['target']['pid'], saved['config']['env'])
    require(len(win) == 1 and win[0]['delete_supported'], 'Screenshot window mismatch')
    raw = subprocess.check_output(['xwd', '-id', win[0]['id'], '-silent'], env=saved['config']['env'], timeout=15)
    exact(common)
    verify_files(saved['config'], saved['baseline'])
    require(owners() == [request['target']['pid']] and windows(request['target']['pid'], saved['config']['env']) == win,
            'Ownership/window changed during screenshot')
    emit('screenshot', xwd=base64.b64encode(raw).decode(), window=win[0]['id'],
         files_preserved=True, argv_preserved=True, environment_preserved=True)
'''
motion.REMOTE_SOURCE = (motion.REMOTE_SOURCE.split("if __name__ == '__main__':",1)[0] + EXTRA +
    motion.REMOTE_EXTENSION[motion.REMOTE_EXTENSION.index("if __name__ == '__main__':"):])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    directory = args.directory
    receipt = rollback.board.load(directory/'receipt.json')
    if receipt['status'] != 'success':
        raise RuntimeError('Successful rollback required')
    resume = rollback.board.load(directory/'resume.json')
    snapshot = next(e for e in resume['events'] if e['state'] == 'snapshot_saved')
    target = resume['events'][-1]
    events = []
    client = rollback.deploy.ssh_connect(timeout=8)
    try:
        identity = rollback.board.load(rollback.LOG/'board_identity.json')
        identity['driver'] = rollback.board.MODULE
        if not rollback.board.endpoint(rollback.board.Remote(client), identity):
            raise RuntimeError('Recovery endpoint/driver/node identity mismatch')
        motion.remote_run(client, dict(action='rollback_screenshot', timeout=60, target=target,
            snapshot=snapshot['snapshot'], snapshot_sha256=snapshot['snapshot_sha256'],
            start_operation=receipt['operation']), events.append)
    finally:
        client.close()
    shot = next(e for e in events if e['state'] == 'screenshot')
    raw = base64.b64decode(shot.pop('xwd'))
    (directory/'screen.xwd').write_bytes(raw)
    fields = struct.unpack('>25I', raw[:100])
    header, version, _, _, width, height, _, order = fields[:8]
    bpp, stride = fields[11:13]
    if (version,bpp,order,*fields[14:17]) != (7,32,0,0xff0000,0xff00,0xff):
        raise RuntimeError('Unexpected XWD pixel format')
    Image.frombytes('RGB',(width,height),raw[header+fields[19]*12:], 'raw','BGRX',stride,1).save(directory/'screen.png')
    text = (directory/'observation.log').read_text(encoding='utf-8')
    summary = motion.candidate.summarize(text)
    observed = rollback.board.load(directory/'observe.json')['events'][-1]
    summary['health'] = health_summary(text, observed)
    summary.update(screenshot=shot, viewer=target, receipt=str(directory/'receipt.json'))
    summary['endpoint'] = dict(identity=identity, verified=True)
    (directory/'metrics.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print('Screenshot and metrics: ' + str(directory), flush=True)

if __name__ == '__main__':
    main()
