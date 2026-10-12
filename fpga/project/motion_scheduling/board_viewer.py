"""Receipt-pinned motion detview switch. --check/--self-test never use SSH."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'project/tools'))
import current_viewer_session as viewer

# Reuse the audited process/observation routines, without either remote main.
spec = importlib.util.spec_from_file_location('motion_candidate_helpers', ROOT / 'project/performance_100h/board_session.py')
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)
LOG = ROOT / 'log/100h_motion'
CAM_RECEIPT = LOG / 'show_camview_ec0dadc39f9346a690b2df8f68470f31.json'
STEREO = '/userdata/linaro/detview-todo-work/src/stereo_pairs.example.json'
MODEL = '/root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v4_combo-rk3568-raw-dfl6-int8.rknn'
MODEL_HASH = '21451a51f680ececd9ee75bcbb4db3e4ccee05d210ef9ffef2f1b99da61a8b31'


def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def valid_hash(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('Full SHA256 required')
    return value


def validate_build(build):
    digest = valid_hash(build.get('snapshot_sha256'))
    directory = '/userdata/linaro/100h_performance/build_' + digest[:16]
    if build.get('status') != 'built' or build.get('remote_directory') != directory or build.get('binary') != directory + '/build/detview':
        raise ValueError('Expected successful immutable build_host.py receipt')
    valid_hash(build.get('binary_sha256'))
    manifest = build.get('source_sha256')
    if not isinstance(manifest, dict) or not manifest or 'detview.pro' not in manifest:
        raise ValueError('Source manifest required')
    for name, value in manifest.items():
        if not isinstance(name, str) or name.startswith('/') or '\\' in name or any(p in ('', '.', '..') for p in name.split('/')):
            raise ValueError('Invalid source manifest path')
        valid_hash(value)
    if hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest() != digest:
        raise ValueError('Source manifest digest mismatch')
    return build


def cam_identity(receipt):
    if receipt.get('action') == 'candidate_stop_restore' and receipt.get('status') == 'success':
        events = [e for e in receipt['events'] if e['state'] == 'restored']
        if len(events) != 1:
            raise ValueError('Unique verified restore event required')
        e = events[0]
        if e['exe_sha256'] != 'dc9ca56440e3b10e2241ef52ad99e1e8fd8e692d0bebda27b9e20fcf88d2e5e9':
            raise ValueError('Restored camview hash mismatch')
        return dict(status='shown', pid=e['pid'], starttime=e['starttime'], sha256=e['exe_sha256'],
                    exe='/userdata/linaro/100h_motion/viewer_eaf579139acf/camview', log=e['log'])
    if receipt.get('exit_code') != 0:
        raise ValueError('Successful current camview receipt required')
    value = json.loads(receipt['output'])
    if (value.get('status') != 'shown' or value.get('pid') != 51952 or value.get('starttime') != '15757898'
            or value.get('sha256') != 'dc9ca56440e3b10e2241ef52ad99e1e8fd8e692d0bebda27b9e20fcf88d2e5e9'
            or value.get('exe') != '/userdata/linaro/100h_motion/viewer_eaf579139acf/camview'):
        raise ValueError('Current camview receipt identity mismatch')
    return value


REMOTE_EXTENSION = r'''
candidate_action = action
candidate_exact = exact
motion_process_before_exit_guard = process

def process(pid):
    try:
        return motion_process_before_exit_guard(pid)
    except (FileNotFoundError, ProcessLookupError):
        require(not Path('/proc', str(pid)).exists(), 'Process identity disappeared while PID remains')
        return None

def exact(request):
    current = candidate_exact(request)
    require(current['pid'] == request['target']['pid'], 'Wrong PID returned by identity inspection')
    return current

original_measurement_quiescent = measurement_quiescent
progress_at = 0
def measurement_quiescent():
    global progress_at
    original_measurement_quiescent()
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            name = (entry / 'comm').read_text().strip()
            args = (entry / 'cmdline').read_bytes().split(b'\0')
        except (FileNotFoundError, ProcessLookupError):
            continue
        require(name not in {'gcc', 'g++', 'cc', 'c++', 'ninja', 'cmake', 'rknn_bench'} and
                not any(v in {b'--motion-policy-selftest', b'--motion-selftest'} for v in args),
                'Compiler/extra inference interferes with observation: PID ' + entry.name)
    now = time.monotonic()
    if now - progress_at >= 10:
        progress_at = now
        print(json.dumps(dict(state='observation_progress', monotonic=now)), flush=True)

def config_for(snap, log):
    return dict(pid=snap['pid'], exe=snap['exe'], argv=snap['argv'], cwd=snap['cwd'],
                env=snap['environment'], log=log)

def private_write(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())

def private_read(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and stat.S_IMODE(info.st_mode) == 0o600,
                'Snapshot must be root-owned private regular file')
        return json.load(stream)

def checked_cam(expected):
    snap = process(expected['pid'])
    require(snap is not None, 'Expected current camview absent')
    for key, value in [('pid', expected['pid']), ('starttime', expected['starttime']),
                       ('exe', expected['exe']), ('exe_sha256', expected['sha256']), ('uid', 0)]:
        require(snap[key] == value, 'Current camview mismatch: ' + key)
    require(snap['argv'] and snap['argv'][0] == snap['exe'], 'Camview argv mismatch')
    env = snap['environment']
    require(env.get('DISPLAY') and env.get('XAUTHORITY', '').startswith('/'), 'Current X11 environment missing')
    snap['files'] = {snap['exe']: sha(snap['exe'])}
    for argument in snap['argv'][1:]:
        if argument.startswith('/') and Path(argument).is_file():
            snap['files'][argument] = sha(argument)
    require(snap['files'][snap['exe']] == snap['exe_sha256'], 'Camview disk hash changed')
    config = config_for(snap, expected['log'])
    exact(dict(config=config, baseline=snap, target=snap))
    require(owners() == [snap['pid']], 'Camview is not sole DMA owner')
    win = windows(snap['pid'], env)
    require(len(win) == 1 and win[0]['delete_supported'], 'Camview lacks unique WM_DELETE window')
    snap['windows'] = win
    return snap

def close_exact(config, snap, target, emit):
    if process(target['pid']) is None:
        require(not owners(), 'Exited candidate but DMA remains owned')
        emit('stopped', pid=target['pid'], starttime=target['starttime'], device_unowned=True, already_exited=True)
        return
    # The original stop has immediate identity/owner/window revalidation and no signals.
    exact(dict(config=config, baseline=snap, target=target))
    original_action(dict(action='stop', config=config, baseline=snap, target=target, timeout=45), emit)

def action(request, emit):
    mode = request['action']
    path = request['snapshot']
    if mode == 'start':
        snap = checked_cam(request['cam'])
        build = request['build']
        argv = [build['binary'], '--model', 'wb_v4_combo', '--fullscreen', '--no-tracking',
                '--stereo-config', request['stereo']]
        env = dict(snap['environment'])
        env.update(DETVIEW_TEXTURE_RING=str(request['ring']), DETVIEW_CAPTURE_MAX_FPS=str(request['capture_fps']),
                   DETVIEW_MOTION_GATING='1', DET_BENCH='1')
        config = dict(pid=0, exe=build['binary'], cwd='/userdata/linaro/detview-todo-work/build', argv=argv,
                      env=env, log=request['log'])
        base = dict(snap, exe=config['exe'], exe_sha256=build['binary_sha256'], argv=argv,
                    cwd=config['cwd'], environment=env,
                    files={request['stereo']: request['stereo_sha256'], request['model']: request['model_sha256']})
        base['files'].update({build['remote_directory'] + '/src/' + p: h for p, h in build['source_sha256'].items()})
        verify_files(config, base)
        saved = dict(operation=request['operation'], boot_id=boot(), cam=snap,
                     cam_config=config_for(snap, request['cam']['log']), config=config, baseline=base,
                     build_sha256=request['build_sha256'], target=None)
        private_write(path, saved)
        emit('snapshot_saved', snapshot=path, snapshot_sha256=sha(path), cam_pid=snap['pid'],
             cam_starttime=snap['starttime'], cam_exe_sha256=snap['exe_sha256'])
        close_exact(saved['cam_config'], snap, snap, emit)
        # Identity sidecar is exclusive and survives later readiness failure.
        def started(state, **details):
            if state == 'candidate_identity':
                private_write(path + '.candidate', dict(operation=request['operation'], **details))
            emit(state, **details)
        candidate_action(dict(action='start', config=config, baseline=base, timeout=30,
                              ready_seconds=5, log=request['log']), started)
        return
    require(sha(path) == request['snapshot_sha256'], 'Snapshot hash mismatch')
    saved = private_read(path)
    require(saved['operation'] == request['start_operation'] and saved['boot_id'] == boot(), 'Snapshot operation/boot mismatch')
    if mode == 'resume_start':
        require(not Path(path + '.candidate').exists(), 'Candidate identity already exists')
        require(process(saved['cam']['pid']) is None, 'Saved camview is still present')
        require(not owners(), 'DMA already owned')
        verify_files(saved['config'], saved['baseline'])
        def resumed(state, **details):
            if state == 'candidate_identity':
                private_write(path + '.candidate', dict(operation=saved['operation'], **details))
            emit(state, **details)
        candidate_action(dict(action='start', config=saved['config'], baseline=saved['baseline'], timeout=30,
                              ready_seconds=5, log=saved['config']['log']), resumed)
        return
    target = private_read(path + '.candidate')
    require(target['operation'] == saved['operation'], 'Candidate sidecar mismatch')
    for key in ('pid', 'starttime', 'exe_sha256'):
        require(target[key] == request['target'][key], 'Receipt candidate mismatch: ' + key)
    common = dict(config=saved['config'], baseline=saved['baseline'], target=target)
    if mode == 'experiment_switch':
        config = dict(saved['config'])
        env = dict(config['env'], DETVIEW_MOTION_GATING=str(request['gating']))
        if 'bench' in request:
            env['DET_BENCH'] = str(request['bench'])
        if 'capture_fps' in request:
            env['DETVIEW_CAPTURE_MAX_FPS'] = str(request['capture_fps'])
        if 'camera_fps' in request:
            env['DETVIEW_CAPTURE_FPS_BY_CAMERA'] = request['camera_fps']
        if 'hud_batch' in request:
            env['DETVIEW_HUD_BATCH'] = str(request['hud_batch'])
        if 'gpu_hud' in request:
            env['DETVIEW_GPU_HUD'] = str(request['gpu_hud'])
        if 'texture_ring' in request:
            env['DETVIEW_TEXTURE_RING'] = str(request['texture_ring'])
        if 'presentation_trace' in request:
            env['DETVIEW_PRESENTATION_TRACE'] = str(request['presentation_trace'])
        if 'swap_interval' in request:
            env['DETVIEW_SWAP_INTERVAL'] = str(request['swap_interval'])
        if 'update_idle_ms' in request:
            env['QT_QPA_UPDATE_IDLE_TIME'] = str(request['update_idle_ms'])
        if 'bypass_compositor' in request:
            env['DETVIEW_BYPASS_COMPOSITOR'] = str(request['bypass_compositor'])
        config.update(env=env, log=request['log'], pid=0)
        base = dict(saved['baseline'], environment=env)
        if 'egl_probe' in request:
            probe = request['egl_probe']
            require(probe['library'].startswith('/userdata/linaro/100h_performance/egl_probe_') and probe['library'].endswith('/libegl_probe.so'), 'Unexpected probe library path')
            env['DETVIEW_EGL_TRACE'] = '1'
            preloads = [p for p in env.get('LD_PRELOAD', '').split(':') if p and p != probe['library']]
            env['LD_PRELOAD'] = ':'.join([probe['library']] + preloads)
            files = dict(base['files'])
            files[probe['library']] = probe['library_sha256']
            files[probe['source']] = probe['source_sha256']
            base.update(files=files)
        if request.get('egl_trace') == 0:
            env['DETVIEW_EGL_TRACE'] = '0'
            preloads = [p for p in env.get('LD_PRELOAD', '').split(':') if p and not p.startswith('/userdata/linaro/100h_performance/egl_probe_')]
            if preloads:
                env['LD_PRELOAD'] = ':'.join(preloads)
            else:
                env.pop('LD_PRELOAD', None)
        if 'build' in request:
            build = request['build']
            config.update(exe=build['binary'], argv=[build['binary']] + config['argv'][1:])
            files = {p: h for p, h in base['files'].items() if not p.startswith('/userdata/linaro/100h_performance/build_')}
            files.update({build['remote_directory'] + '/src/' + p: h for p,h in build['source_sha256'].items()})
            base.update(exe=config['exe'], exe_sha256=build['binary_sha256'], argv=config['argv'], files=files)
        verify_files(config, base)
        replacement = dict(saved, operation=request['operation'], config=config, baseline=base, target=None)
        private_write(request['new_snapshot'], replacement)
        emit('snapshot_saved', snapshot=request['new_snapshot'], snapshot_sha256=sha(request['new_snapshot']),
             gating=request['gating'], hud_batch=request.get('hud_batch'))
        close_exact(saved['config'], saved['baseline'], target, emit)
        def switched(state, **details):
            if state == 'candidate_identity':
                private_write(request['new_snapshot'] + '.candidate', dict(operation=request['operation'], **details))
            emit(state, **details)
        candidate_action(dict(action='start', config=config, baseline=base, timeout=30,
                              ready_seconds=5, log=request['log']), switched)
        return
    if mode == 'observe':
        candidate_action(dict(common, action='observe', log=saved['config']['log'], seconds=request['seconds'],
                              max_bytes=16 * 1024 * 1024), emit)
        return
    require(mode == 'candidate_stop_restore', 'Unknown action')
    verify_files(saved['cam_config'], saved['cam'])
    close_exact(saved['config'], saved['baseline'], target, emit)
    original_action(dict(action='restore', config=saved['cam_config'], baseline=saved['cam'],
                         target=target, restore_log=request['log'], timeout=30), emit)

if __name__ == '__main__':
    def emit(state, **details):
        print(json.dumps(dict(state=state, **details)), flush=True)
    try:
        request = json.loads(sys.stdin.read().splitlines()[-1])
        def expired(signum, frame):
            raise TimeoutError('Bound exceeded; any launched process left untouched')
        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, request['timeout'])
        action(request, emit)
    except BaseException as exc:
        emit('failed', error=str(exc))
        sys.exit(1)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
'''
OBSERVE_SOURCE = candidate.REMOTE_EXTENSION.split("if __name__ == '__main__':", 1)[0]
OBSERVE_SOURCE = OBSERVE_SOURCE.replace("time.sleep(min(1, request['seconds'] - elapsed))",
                                        "time.sleep(min(5, request['seconds'] - elapsed))")
REMOTE_SOURCE = (viewer.REMOTE_SOURCE.split("if __name__ == '__main__':", 1)[0]
                 + OBSERVE_SOURCE + REMOTE_EXTENSION)


def remote_run(client, request, event):
    stdin, stdout, stderr = client.exec_command("sudo -S -p '' python3 -c " + shlex.quote(REMOTE_SOURCE), timeout=15)
    channel = stdout.channel
    deadline = time.monotonic() + request['timeout'] + 20
    pending = b''
    try:
        stdin.write('123456\n' + json.dumps(request) + '\n')
        stdin.flush()
        channel.shutdown_write()
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError('SSH bound exceeded; review retained receipt before retry')
            if channel.recv_ready():
                pending += channel.recv(65536)
                while b'\n' in pending:
                    line, pending = pending.split(b'\n', 1)
                    if line:
                        event(json.loads(line))
            if channel.recv_stderr_ready():
                channel.recv_stderr(65536)  # Do not print remote diagnostics/environment.
            if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                code = channel.recv_exit_status()
                if pending:
                    event(json.loads(pending))
                if code:
                    raise RuntimeError('Remote action failed; see retained receipt')
                return
            time.sleep(.05)
    finally:
        channel.close()


def run(args):
    token = uuid.uuid4().hex
    mode = args.action
    LOG.mkdir(parents=True, exist_ok=True)
    path = LOG / ('motion_viewer_' + mode + '_' + token + '.json')
    receipt = dict(schema=1, action=mode, operation=token, status='running', events=[])
    request = dict(action=mode, operation=token, timeout=args.seconds + 60 if mode == 'observe' else 100)
    client = None
    lock = LOG / 'board_session.lock'
    held = False
    try:
        if mode in ('start', 'check'):
            if args.build_receipt is None or args.stereo_sha256 is None:
                raise ValueError('Start/check require --build-receipt and --stereo-sha256')
            build = validate_build(viewer.read_json(args.build_receipt))
            cam = cam_identity(viewer.read_json(args.cam_receipt or CAM_RECEIPT))
            valid_hash(args.stereo_sha256)
            request.update(build=build, build_sha256=sha_file(args.build_receipt), cam=cam,
                           ring=args.ring, capture_fps=args.capture_fps, stereo=STEREO,
                           stereo_sha256=args.stereo_sha256, model=MODEL, model_sha256=MODEL_HASH,
                           snapshot='/userdata/linaro/100h_performance/motion_viewer_' + token + '.snapshot.json',
                           log='/userdata/linaro/100h_performance/motion_viewer_' + token + '.log')
            receipt.update(build_receipt_sha256=request['build_sha256'])
            if mode == 'check':
                print(json.dumps(dict(valid=True, ssh=False, binary=build['binary'])))
                receipt['status'] = 'success'
                return
        else:
            if args.start_receipt is None:
                raise ValueError('Observe/restore require --start-receipt')
            start = viewer.read_json(args.start_receipt)
            if start.get('schema') != 1 or start.get('action') != 'start':
                raise ValueError('Motion viewer start receipt required')
            if not re.fullmatch('[0-9a-f]{32}', str(start.get('operation', ''))):
                raise ValueError('Invalid start operation token')
            snapshots = [e for e in start['events'] if e['state'] == 'snapshot_saved']
            targets = [e for e in start['events'] if e['state'] in ('candidate_identity', 'started')]
            if len(snapshots) != 1 or (not targets and mode != 'resume_start'):
                raise ValueError('Receipt lacks captured snapshot/candidate identity; review manually')
            snapshot, target = snapshots[0], targets[-1] if targets else None
            valid_hash(snapshot['snapshot_sha256'])
            if target:
                valid_hash(target['exe_sha256'])
            expected_path = '/userdata/linaro/100h_performance/motion_viewer_' + start['operation'] + '.snapshot.json'
            if snapshot['snapshot'] != expected_path or (target and (type(target['pid']) is not int or target['pid'] <= 0 or not str(target['starttime']).isdigit())):
                raise ValueError('Receipt path/PID/starttime invalid')
            request.update(snapshot=expected_path, snapshot_sha256=snapshot['snapshot_sha256'],
                           start_operation=start['operation'], target=target, seconds=args.seconds,
                            log='/userdata/linaro/100h_performance/camview_restore_' + token + '.log')
            if mode == 'experiment_switch':
                request.update(gating=args.gating, new_snapshot='/userdata/linaro/100h_performance/motion_viewer_' + token + '.snapshot.json',
                               log='/userdata/linaro/100h_performance/motion_viewer_' + token + '.log')
                receipt.update(action='start', experiment_gating=args.gating,
                               inherited_start_receipt=str(args.start_receipt))
                if args.hud_batch is not None:
                    request['hud_batch'] = args.hud_batch
                    receipt['experiment_hud_batch'] = args.hud_batch
                if args.gpu_hud is not None:
                    request['gpu_hud'] = args.gpu_hud
                    receipt['experiment_gpu_hud'] = args.gpu_hud
                if args.texture_ring is not None:
                    request['texture_ring'] = args.texture_ring
                    receipt['experiment_texture_ring'] = args.texture_ring
                if args.presentation_trace is not None:
                    request['presentation_trace'] = args.presentation_trace
                    receipt['experiment_presentation_trace'] = args.presentation_trace
                if args.swap_interval is not None:
                    request['swap_interval'] = args.swap_interval
                    receipt['experiment_swap_interval'] = args.swap_interval
                if args.update_idle_ms is not None:
                    request['update_idle_ms'] = args.update_idle_ms
                    receipt['experiment_update_idle_ms'] = args.update_idle_ms
                if args.bypass_compositor is not None:
                    request['bypass_compositor'] = args.bypass_compositor
                    receipt['experiment_bypass_compositor'] = args.bypass_compositor
                if args.egl_probe_receipt is not None:
                    probe = json.loads(Path(args.egl_probe_receipt).read_text(encoding='utf-8'))
                    valid_hash(probe['library_sha256'])
                    valid_hash(probe['source_sha256'])
                    request['egl_probe'] = probe
                    receipt['experiment_egl_probe'] = probe
                if args.egl_trace is not None:
                    request['egl_trace'] = args.egl_trace
                if args.bench is not None:
                    request['bench'] = args.bench
                    receipt['experiment_bench'] = args.bench
                if args.camera_fps is not None:
                    values = args.camera_fps.split(',')
                    if len(values) != 6 or any(not v.isdigit() or not 10 <= int(v) <= 60 for v in values):
                        raise ValueError('Six integer per-camera limits in range10..60 required')
                    request['camera_fps'] = args.camera_fps
                    receipt['experiment_camera_fps'] = args.camera_fps
                if args.experiment_capture_fps is not None:
                    request['capture_fps'] = args.experiment_capture_fps
                    receipt['experiment_capture_fps'] = args.experiment_capture_fps
                if args.build_receipt is not None:
                    request['build'] = validate_build(viewer.read_json(args.build_receipt))
                    receipt['build_receipt_sha256'] = sha_file(args.build_receipt)
            receipt.update(start_receipt_sha256=sha_file(args.start_receipt))
        from board_host import board_host, ssh_connect
        receipt['host'] = board_host()
        if mode != 'start' and start.get('host') != receipt['host']:
            raise ValueError('Start receipt board host mismatch')
        with lock.open('x', encoding='utf-8') as stream:
            json.dump(dict(operation=token, pid=os.getpid(), action=mode), stream)
        held = True
        viewer.atomic_json(path, receipt)
        def event(value):
            receipt['events'].append(value)
            viewer.atomic_json(path, receipt)
            if value['state'] != 'log_chunk':
                print('Motion viewer: ' + value['state'], flush=True)
        client = ssh_connect()
        remote_run(client, request, event)
        expected = dict(start='started', resume_start='started', experiment_switch='started', observe='observed', candidate_stop_restore='restored')[mode]
        if not receipt['events'] or receipt['events'][-1]['state'] != expected:
            raise RuntimeError('No verified remote outcome')
        if mode == 'observe':
            text = ''.join(e['text'] for e in receipt['events'] if e['state'] == 'log_chunk')
            generations = [int(v) for v in re.findall(r'\bgeneration=(\d+)', text)]
            receipt['log_summary'] = dict(
                motion_generations=dict(count=len(generations), first=generations[0] if generations else None,
                                        last=generations[-1] if generations else None),
                policy_lines=[line for line in text.splitlines() if '[motion-scheduling]' in line],
                traffic_lines=[line for line in text.splitlines() if '[motion-traffic]' in line],
                probe_lines=[line for line in text.splitlines() if '[motion-probe]' in line])
        receipt['status'] = 'success'
    except BaseException as exc:
        receipt.update(status='failed', error=str(exc))
        raise
    finally:
        viewer.atomic_json(path, receipt)
        print('Session receipt: ' + str(path))
        if client:
            client.close()
        if held and viewer.read_json(lock).get('operation') == token:
            lock.unlink()


def self_test():
    import copy
    import unittest
    from unittest.mock import Mock, patch
    ns = {'__name__': 'motion_local_test'}
    exec(compile(REMOTE_SOURCE, '<motion remote>', 'exec'), ns)
    class Tests(unittest.TestCase):
        def test_process_exit_race(self):
            from tempfile import TemporaryDirectory
            with TemporaryDirectory() as directory:
                # A read racing a fully exited PID returns absent; a surviving
                # PID whose identity cannot be read must still fail closed.
                with patch.dict(ns, motion_process_before_exit_guard=Mock(side_effect=FileNotFoundError),
                                Path=lambda *parts: Path(directory) / str(parts[-1])):
                    self.assertIsNone(ns['process'](987654))
                    (Path(directory) / '987654').mkdir()
                    with self.assertRaises(RuntimeError):
                        ns['process'](987654)
        def test_build_paths(self):
            manifest = {'detview.pro': 'a' * 64}
            digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
            directory = '/userdata/linaro/100h_performance/build_' + digest[:16]
            build = dict(status='built', snapshot_sha256=digest, source_sha256=manifest,
                         binary_sha256='b' * 64, remote_directory=directory, binary=directory + '/build/detview')
            validate_build(build)
            for key, value in [('binary', '/tmp/detview'), ('status', 'failed'), ('snapshot_sha256', 'c' * 64)]:
                bad = copy.deepcopy(build); bad[key] = value
                with self.assertRaises(ValueError):
                    validate_build(bad)
        def test_current_receipt(self):
            expected = cam_identity(viewer.read_json(CAM_RECEIPT))
            snap = dict(pid=expected['pid'], starttime='wrong', exe=expected['exe'], exe_sha256=expected['sha256'], uid=0)
            close, write, launch = Mock(), Mock(), Mock()
            with patch.dict(ns, process=lambda pid: snap, close_window=close, private_write=write):
                with patch.object(ns['subprocess'], 'Popen', launch):
                    with self.assertRaises(RuntimeError):
                        ns['action'](dict(action='start', snapshot='/tmp/snapshot', cam=expected), Mock())
            close.assert_not_called(); write.assert_not_called(); launch.assert_not_called()
        def test_snapshot_mismatch_no_action(self):
            close, launch, read = Mock(), Mock(), Mock()
            with patch.dict(ns, sha=lambda path: 'a' * 64, private_read=read, close_window=close):
                with patch.object(ns['subprocess'], 'Popen', launch):
                    with self.assertRaises(RuntimeError):
                        ns['action'](dict(action='candidate_stop_restore', snapshot='/tmp/private', snapshot_sha256='b' * 64), Mock())
            close.assert_not_called(); launch.assert_not_called(); read.assert_not_called()
        def test_restore_wrong_candidate_no_action(self):
            saved = dict(operation='op', boot_id='boot')
            sidecar = dict(operation='op', pid=42, starttime='99', exe_sha256='c' * 64)
            close, launch = Mock(), Mock()
            with patch.dict(ns, sha=lambda path: 'a' * 64, boot=lambda: 'boot',
                            private_read=Mock(side_effect=[saved, sidecar]), close_window=close):
                with patch.object(ns['subprocess'], 'Popen', launch):
                    with self.assertRaises(RuntimeError):
                        ns['action'](dict(action='candidate_stop_restore', snapshot='/tmp/private',
                                          snapshot_sha256='a' * 64, start_operation='op',
                                          target=dict(sidecar, pid=43)), Mock())
            close.assert_not_called(); launch.assert_not_called()
        def test_close_requires_exact_full_identity(self):
            stop = Mock()
            with patch.dict(ns, exact=Mock(side_effect=RuntimeError('Wrong PID')), original_action=stop):
                with self.assertRaises(RuntimeError):
                    ns['close_exact']({}, {}, dict(pid=999), Mock())
            stop.assert_not_called()
        def test_no_force_close(self):
            self.assertNotIn('os.kill', REMOTE_EXTENSION)
            self.assertNotIn('XTestFakeKeyEvent', REMOTE_SOURCE)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    return 0 if result.wasSuccessful() else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'start', 'resume_start', 'experiment_switch', 'observe', 'candidate_stop_restore', 'self-test'])
    parser.add_argument('--gating', type=int, choices=[0, 1], default=1)
    parser.add_argument('--hud-batch', type=int, choices=[0, 1])
    parser.add_argument('--gpu-hud', type=int, choices=[0, 1])
    parser.add_argument('--texture-ring', type=int, choices=[1, 2, 3])
    parser.add_argument('--presentation-trace', type=int, choices=[0, 1])
    parser.add_argument('--swap-interval', type=int, choices=[0, 1])
    parser.add_argument('--update-idle-ms', type=int, choices=[0, 5])
    parser.add_argument('--bypass-compositor', type=int, choices=[0, 1])
    parser.add_argument('--egl-probe-receipt')
    parser.add_argument('--egl-trace', type=int, choices=[0])
    parser.add_argument('--bench', type=int, choices=[0, 1])
    parser.add_argument('--camera-fps')
    parser.add_argument('--experiment-capture-fps', type=int, choices=range(10,61))
    parser.add_argument('--build-receipt', type=Path)
    parser.add_argument('--cam-receipt', type=Path)
    parser.add_argument('--start-receipt', type=Path)
    parser.add_argument('--stereo-sha256')
    parser.add_argument('--ring', type=int, choices=range(1, 5), default=1)
    parser.add_argument('--capture-fps', type=int, choices=range(1, 61), default=30)
    parser.add_argument('--seconds', type=int, default=120)
    args = parser.parse_args()
    if not 120 <= args.seconds <= 300:
        parser.error('--seconds must be in [120, 300]')
    if args.action == 'self-test':
        return self_test()
    try:
        run(args)
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
