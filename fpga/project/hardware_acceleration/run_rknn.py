"""Freeze, build and reversibly run the real RK3568 RKNN I/O experiments."""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'project/tools'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_helpers():
    spec = importlib.util.spec_from_file_location('acceleration_viewer', ROOT / 'project/motion_scheduling/board_viewer.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REMOTE = r'''
import base64

def wait_for_quiet(emit):
    deadline = time.monotonic() + 180
    quiet_since = None
    reported_at = 0
    while True:
        try:
            measurement_quiescent()
            if quiet_since is None:
                quiet_since = time.monotonic()
            if time.monotonic() - quiet_since >= 3:
                emit('board_quiet', stable_seconds=3)
                return
        except RuntimeError as exc:
            quiet_since = None
            if time.monotonic() - reported_at >= 10:
                reported_at = time.monotonic()
                emit('board_busy', reason=str(exc))
        require(time.monotonic() < deadline, 'Board remained busy; probe was not started')
        time.sleep(1)

def fd_import_restoration_proof(request, out, child):
    protected = (request.get('backend') == 'rknn' and request.get('phase') == 'experiment' and
                 'native_io_fd_import' in request.get('candidates', []))
    if not protected or child is None:
        return dict(safe=True, reason='No imported-memory probe was launched', checked_logs=0)
    if child.poll() is None:
        return dict(safe=False, reason='Private probe has not exited', checked_logs=0)
    logs = sorted(path for path in (out/'results').glob('native_io_fd_import_*.stdout')
                  if path.name.endswith(('_cert_candidate.stdout', '_native_io_fd_import.stdout')))
    if not logs:
        return dict(safe=False, reason='No imported-memory retirement proof retained', checked_logs=0)
    for path in logs:
        if path.is_symlink() or path.stat().st_size > 16*1024*1024:
            return dict(safe=False, reason='Invalid imported-memory log type/size', checked_logs=0)
        try:
            rows = [json.loads(line) for line in path.read_text().splitlines() if line.startswith('{')]
        except (ValueError, OSError):
            return dict(safe=False, reason='Incomplete imported-memory log', checked_logs=0)
        retirements = [row for row in rows if row.get('event') == 'dma_heap_retirement']
        if not retirements:
            return dict(safe=False, reason='Imported-memory retirement missing: ' + path.name, checked_logs=0)
        terminal = [row for row in rows if row.get('event') in ('summary', 'unsupported')]
        if len(terminal) != 1 or rows[-1] is not terminal[0]:
            return dict(safe=False, reason='Imported-memory process interrupted or missing terminal evidence: ' + path.name,
                        checked_logs=0)
        domains = [row.get('purpose') for row in rows if row.get('event') == 'dma_heap_session_started']
        domains += [row.get('purpose') for row in rows if row.get('event') == 'memory' and
                    row.get('allocator') == 'dma_heap_system_fd_import']
        purposes = [row.get('purpose') for row in retirements]
        if not domains or not all(domain in purposes for domain in set(domains)) or len(purposes) != len(set(purposes)):
            return dict(safe=False, reason='Imported-memory session retirement coverage incomplete: ' + path.name,
                        checked_logs=0)
        if terminal[0]['event'] == 'summary' and 'native_io_fd_import' not in purposes:
            return dict(safe=False, reason='Inference-session retirement missing: ' + path.name, checked_logs=0)
        for row in retirements:
            if (row.get('retirement_branch') != 'normal' or row.get('cleanup_ok') is not True or
                row.get('context_destroy_attempted') is not True or row.get('context_destroy_rc') != 0 or
                row.get('process_teardown_only') is not False or row.get('runtime_library_retained') is not False or
                row.get('context_retained') is not False or row.get('fatal_no_continue') is not False):
                return dict(safe=False, reason='Device state unresolved after imported-memory retirement: ' + path.name,
                            checked_logs=0)
    return dict(safe=True, reason='All imported-memory runs retired normally', checked_logs=len(logs))

def acceleration(request, emit):
    root = Path(request['package'])
    for name, digest in request['source_sha256'].items():
        require(sha(root / name) == digest, 'Frozen probe source changed: ' + name)
    require(not root.is_symlink(), 'Private probe package is a symlink')
    own = owners()
    require(len(own) == 1, 'One current viewer DMA owner is required')
    snap = process(own[0])
    require(snap['exe'] == '/userdata/detview-hdmifull/detview-hdmifull' and
            snap['exe_sha256'] == request['viewer_sha256'], 'Unexpected current viewer identity')
    require(snap['argv'] == request['viewer_argv'] and snap['uid'] == 0,
            'Unexpected current viewer arguments/credentials')
    require(not snap['environment'].get('LD_PRELOAD'), 'Unexpected viewer preload')
    libraries = []
    for line in Path('/proc', str(snap['pid']), 'maps').read_text().splitlines():
        columns = line.split(None, 5)
        if len(columns) == 6 and columns[5].endswith('/librknnrt.so'):
            libraries.append(str(Path(columns[5]).resolve()))
    libraries = sorted(set(libraries))
    require(len(libraries) == 1, 'Cannot bind a unique viewer RKNN runtime')
    library = libraries[0]
    if request.get('library_sha256'):
        require(sha(library) == request['library_sha256'], 'RKNN runtime changed since build')
    snap['files'] = {snap['exe']: snap['exe_sha256'], request['model']: request['model_sha256']}
    for arg in snap['argv'][1:]:
        path = Path(arg) if arg.startswith('/') else Path(snap['cwd']) / arg
        if path.is_file():
            snap['files'][str(path.resolve())] = sha(path)
    verify_files(config_for(snap, ''), snap)
    win = windows(snap['pid'], snap['environment'])
    require(len(win) == 1 and win[0]['delete_supported'], 'Viewer has no unique normal-close window')
    exact(dict(config=config_for(snap, ''), baseline=snap, target=snap))
    require(owners() == [snap['pid']], 'DMA owner changed during preflight')
    phase = request['phase']
    config = config_for(snap, '')
    saved = dict(operation=request['operation'], boot_id=boot(), baseline=snap, config=config)
    private_write(request['snapshot'], saved)
    emit('snapshot_saved', snapshot=request['snapshot'], snapshot_sha256=sha(request['snapshot']),
         pid=snap['pid'], starttime=snap['starttime'], exe_sha256=snap['exe_sha256'],
         library=library, library_sha256=sha(library))
    out = Path(request['output'])
    out.mkdir(parents=True, exist_ok=False)
    if request.get('backend') == 'rga_copy':
        require(phase == 'experiment', 'RGA copy backend builds and tests cached heap buffers in one isolated experiment')
        command = ['python3', str(root / 'run_target.py'), '--phase', 'experiment', '--board-exclusive',
                   '--sourcepath', str(root), '--out', str(out / 'results')]
    elif request.get('backend') == 'dma_export':
        require(phase == 'build', 'DMA exporter backend compiles privately and never loads a module')
        command = ['python3', str(root / 'build_dma_export_target.py'), '--source', str(root / 'src'),
                   '--headers', '/usr/src/linux-headers-6.1-rockchip', '--out', str(out / 'results')]
    elif request.get('backend') == 'viewer_parity':
        require(phase == 'experiment', 'Viewer helper backend requires an isolated experiment')
        command = ['python3', str(root / 'run_parity_target.py'), '--phase', 'experiment', '--board-exclusive',
                   '--source', str(root / 'src'), '--fixtures', str(root / 'fixture_suite'),
                   '--model', request['model'], '--lib', library, '--out', str(out / 'results'), '--save-arrays']
    elif request.get('backend') == 'viewer':
        require(phase == 'build', 'Viewer backend is a private build only')
        command = ['python3', str(root / 'build_viewer_target.py'), '--source', str(root / 'src'),
                   '--lib', library, '--out', str(out / 'results')]
    elif request.get('backend') == 'rga':
        command = ['python3', str(root / 'run_board.py'), '--board-free', '--fixtures',
                   str(root / 'local_evidence/fixtures'), '--headers-root', '/usr/include',
                   '--frames', '500', '--warmup', '30', '--memory', 'fd', '--output', str(out / 'results')]
    elif phase == 'diagnose':
        require(sha(request['binary']) == request['binary_sha256'], 'Pinned diagnostic executable changed')
        command = [request['binary'], '--mode', request['diagnostic_mode'], '--lib', library,
                   '--model', request['model'], '--manifest', str(root / 'prepared/manifest.json'),
                   '--native-query', str(request['native_query']),
                   '--fixture', str(root / 'prepared/fixtures/bright_baseline_cam1.png'), '--kind', 'png',
                   '--warmup', '1', '--iterations', '1', '--snapshot-all', '--prefix', str(out / 'native')]
        command += ['--dequant-scale', request['dequant_scale']]
        command += request['diagnostic_options']
    else:
        command = ['python3', str(root / 'run_target.py'), 'build' if phase == 'build' else 'experiment',
                   '--board-exclusive', '--lib', library, '--model', request['model'], '--out', str(out / 'results')]
    if phase == 'experiment' and request.get('backend') == 'rknn':
        require(sha(request['binary']) == request['binary_sha256'], 'Pinned benchmark executable changed')
        command += ['--binary', request['binary'], '--candidates'] + request['candidates']
        command += ['--native-query', str(request['native_query']), '--iterations', str(request['iterations']),
                     '--rounds', str(request['rounds']), '--dequant-scale', request['dequant_scale']]
        if request.get('timing_reference', 'baseline') != 'baseline':
            command += ['--timing-reference', request['timing_reference']]
    child = None
    closed = False
    try:
        if phase != 'build':
            wait_for_quiet(emit)
            close_exact(config, snap, snap, emit)
            closed = True
            require(not owners(), 'DMA remains occupied after normal closure')
            measurement_quiescent()
        with open(out / 'supervisor.stdout', 'xb', buffering=0) as stdout, open(out / 'supervisor.stderr', 'xb', buffering=0) as stderr:
            child = subprocess.Popen(command, cwd=str(root), stdout=stdout, stderr=stderr,
                                     stdin=subprocess.DEVNULL, start_new_session=True,
                                     env=snap['environment'] if request.get('backend') == 'viewer' else None)
            started_at = time.monotonic()
            emit('probe_started', pid=child.pid, phase=phase, output=str(out), command=command)
            deadline = time.monotonic() + (1200 if request.get('backend') == 'viewer' else 600 if phase == 'build' else 1800)
            progress_at = 0
            while child.poll() is None:
                require(time.monotonic() < deadline, 'Probe time limit exceeded')
                if time.monotonic() - progress_at >= 10:
                    progress_at = time.monotonic()
                    if phase != 'build' and request.get('backend') == 'rknn':
                        measurement_quiescent()
                    log = (out / 'supervisor.stdout').read_text(errors='replace')
                    progress = [line for line in log.splitlines() if line.startswith('{')]
                    emit('probe_progress', phase=phase, elapsed_seconds=time.monotonic() - started_at,
                         latest=progress[-1][:1200] if progress else ('compiling' if phase == 'build' else 'running hardware probe'))
                time.sleep(.2)
            emit('probe_finished', exit_code=child.returncode, phase=phase)
            require(child.returncode == 0, 'Probe failed; raw artifacts retained')
    finally:
        try:
            if child is not None and child.poll() is None:
                # Only the private benchmark process group is terminated, never a viewer.
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    child.wait(timeout=10)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 100)
            try:
                proof = fd_import_restoration_proof(request, out, child)
                if not proof['safe']:
                    emit('restoration_held', reason=proof['reason'], private_probe_exited=child is not None and child.poll() is not None,
                         hardware_quiescence_proven=False, board_lock_must_remain=True)
                    raise RuntimeError('Viewer restoration withheld: ' + proof['reason'])
                if proof['checked_logs']:
                    emit('import_retirement_checked', **proof)
                if closed or process(snap['pid']) is None:
                    emit('restoration_started', snapshot=request['snapshot'])
                    verify_files(config, snap)
                    original_action(dict(action='restore', config=config, baseline=snap, target=snap,
                                          restore_log=request['restore_log'], timeout=45), emit)
                else:
                    exact(dict(config=config, baseline=snap, target=snap))
                    require(owners() == [snap['pid']], 'Current viewer changed during private build')
                    emit('viewer_preserved', pid=snap['pid'], starttime=snap['starttime'])
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)

def emit_private_artifacts(request, emit):
    out = Path(request['output'])
    if not out.is_dir():
        return
    files = []
    for path in sorted(out.rglob('*')):
        if path.is_file() and path.suffix in {'.json', '.jsonl', '.stdout', '.stderr', '.f32', '.u8', '.bin', '.maps', '.cmd', '.ko', '.d'}:
            require(not path.is_symlink() and path.resolve().is_relative_to(out.resolve()) and
                    path.stat().st_uid == 0 and path.stat().st_size <= 128*1024*1024,
                    'Private artifact owner/bound/type violation')
            files.append(dict(name=path.relative_to(out).as_posix(), path=str(path),
                              bytes=path.stat().st_size, sha256=sha(path)))
    emit('artifacts', files=files)

def action(request, emit):
    if request.get('action') == 'download':
        import re
        import stat
        item = request['artifact']
        require(re.fullmatch(r'/userdata/linaro/100h_performance/hardware_[0-9a-f]{32}/run/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+', item['path']),
                'Invalid private acceleration artifact path')
        require(all(v not in {'.', '..'} for v in item['path'].split('/')), 'Artifact path traversal')
        fd = os.open(item['path'], os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and
                    info.st_size == item['bytes'] and info.st_size <= 128*1024*1024,
                    'Private acceleration artifact owner/type/size differs')
            require(sha('/proc/self/fd/' + str(stream.fileno())) == item['sha256'], 'Private artifact hash changed')
            for block in iter(lambda: stream.read(65536), b''):
                emit('artifact_chunk', base64=base64.b64encode(block).decode('ascii'))
        emit('downloaded', sha256=item['sha256'])
        return
    try:
        acceleration(request, emit)
    finally:
        emit_private_artifacts(request, emit)

if __name__ == '__main__':
    def emit(state, **details):
        try:
            print(json.dumps(dict(state=state, **details)), flush=True)
        except (BrokenPipeError, OSError):
            pass
    def expired(signum, frame):
        raise TimeoutError('Accelerator supervisor deadline/interruption')
    try:
        request = json.loads(sys.stdin.read().splitlines()[-1])
        for number in (signal.SIGALRM, signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            signal.signal(number, expired)
        signal.setitimer(signal.ITIMER_REAL, request['timeout'] if request.get('action') == 'download' else request['timeout'] - 110)
        action(request, emit)
    except BaseException as exc:
        emit('failed', error=type(exc).__name__ + ': ' + str(exc))
        sys.exit(1)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=('rknn', 'rga', 'rga_copy', 'viewer', 'viewer_parity', 'dma_export'), default='rknn')
    parser.add_argument('--source', type=Path, help='Complete frozen viewer or DMA-exporter source tree')
    parser.add_argument('--phase', choices=('build', 'experiment', 'diagnose'), required=True)
    parser.add_argument('--build-receipt', type=Path)
    parser.add_argument('--candidates', nargs='+', choices=('prealloc', 'native', 'native_io', 'native_io_single_copy', 'native_io_fd_import'), default=['prealloc'])
    parser.add_argument('--timing-reference', choices=('baseline', 'native_io', 'native_io_single_copy'), default='baseline',
                        help='Certification always uses legacy; optionally isolate input-copy timing against native_io')
    parser.add_argument('--native-query', type=int, choices=(9, 11), default=9)
    parser.add_argument('--iterations', type=int, default=50)
    parser.add_argument('--rounds', type=int, default=4)
    parser.add_argument('--dequant-scale', choices=('fp32', 'fp16'), default='fp32')
    parser.add_argument('--diagnostic-mode', choices=('native', 'native_io'), default='native')
    parser.add_argument('--diagnostic-options', default='[]',
                        help='JSON string array of extra native diagnostic benchmark options')
    args = parser.parse_args()
    if args.backend == 'rga' and args.phase != 'experiment':
        parser.error('RGA runner freezes, builds and runs in the experiment phase')
    if args.backend == 'rga_copy' and args.phase != 'experiment':
        parser.error('RGA same-format copy freezes, builds and tests cached heap buffers in one experiment')
    if args.backend == 'viewer' and (args.phase != 'build' or args.source is None):
        parser.error('Viewer requires --phase build --source with a complete frozen tree')
    if args.backend == 'viewer_parity' and (args.phase != 'experiment' or args.source is None):
        parser.error('Viewer helper requires --phase experiment --source with a complete frozen tree')
    if args.backend == 'dma_export' and (args.phase != 'build' or args.source is None):
        parser.error('DMA exporter requires --phase build --source; this backend never loads a module')
    if args.phase != 'build' and args.backend == 'rknn' and args.build_receipt is None:
        parser.error('Experiment requires a successful immutable build receipt')
    allowed_controls = {('native_io', ('native_io_single_copy',)),
                        ('native_io_single_copy', ('native_io_fd_import',))}
    if args.timing_reference != 'baseline' and (args.backend != 'rknn' or args.phase != 'experiment' or
            (args.timing_reference, tuple(args.candidates)) not in allowed_controls):
        parser.error('Native timing control must isolate single-copy or FD-import allocation changes')
    if 'native_io_fd_import' in args.candidates and (args.backend != 'rknn' or args.phase != 'experiment' or
            args.timing_reference != 'native_io_single_copy' or args.native_query != 9 or args.dequant_scale != 'fp16'):
        parser.error('FD import requires native_io_single_copy timing control, native-query9 and FP16 scales')
    diagnostic_options = json.loads(args.diagnostic_options)
    if not isinstance(diagnostic_options, list) or any(not isinstance(value, str) or '\0' in value for value in diagnostic_options):
        parser.error('--diagnostic-options must be a JSON string array')
    motion = load_helpers()
    from board_host import board_host, ssh_connect
    token = uuid.uuid4().hex
    directory = TASK / 'runs' / (args.backend + '_' + args.phase + '_' + token)
    directory.mkdir(parents=True)
    receipt_path = directory / 'receipt.json'
    remote = '/userdata/linaro/100h_performance/hardware_' + token
    receipt = dict(schema=1, operation=token, backend=args.backend, phase=args.phase, status='running', host=board_host(),
                   remote_directory=remote, events=[], full_viewer_fps_claim=False)
    request = dict(backend=args.backend, phase=args.phase, operation=token, timeout=2100, output=remote + '/run',
                   snapshot=remote + '/viewer.snapshot.json', restore_log=remote + '/viewer.restore.log',
                   model='/root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v4_combo-rk3568-raw-dfl6-int8.rknn',
                   model_sha256='21451a51f680ececd9ee75bcbb4db3e4ccee05d210ef9ffef2f1b99da61a8b31',
                   viewer_sha256='0301f6901330ff161b76f1fb343edb5f0acbf93064b04794c98147da6e92a737',
                   viewer_argv=['/userdata/detview-hdmifull/detview-hdmifull', '--model', 'wb_v4_combo',
                                '--fullscreen', '--no-tracking', '--prefer-hdmifull', 'auto'],
                   candidates=args.candidates, native_query=args.native_query,
                   iterations=args.iterations, rounds=args.rounds,
                   diagnostic_mode=args.diagnostic_mode, diagnostic_options=diagnostic_options,
                    dequant_scale=args.dequant_scale, timing_reference=args.timing_reference)
    blobs = {}
    if args.phase == 'build' or args.backend in ('rga', 'rga_copy', 'viewer_parity'):
        viewer_backend = args.backend in ('viewer', 'viewer_parity')
        package = args.source.resolve() if viewer_backend or args.backend == 'dma_export' else TASK / (args.backend if args.backend in ('rga', 'rga_copy') else 'rknn_io')
        viewer_complete_tree = viewer_backend and (package / 'src/detview.pro').is_file()
        for path in sorted(package.rglob('*')):
            name = path.relative_to(package).as_posix()
            if args.backend == 'rga' and not (name.startswith('local_evidence/fixtures/') or
                                              '/' not in name and path.suffix in {'.cpp', '.hpp', '.py', '.md'}):
                continue
            if args.backend == 'rga_copy' and name not in {'same_format_copy.h', 'probe.cpp', 'run_target.py', 'README.md'}:
                continue
            retained_fd_checks = args.backend == 'rknn' and name == 'local_tests/fd_import_checks.py'
            if path.is_file() and (retained_fd_checks or not any(part in {'receipts', '__pycache__', 'local_tests', 'board_runs'} for part in path.relative_to(package).parts)):
                blobs[('src/' + name) if (viewer_backend and not viewer_complete_tree) or args.backend == 'dma_export' else name] = path.read_bytes()
        if viewer_backend:
            if not viewer_complete_tree:
                sdk = package.parent / 'sdk/rknn_api.h'
                if not sdk.is_file():
                    raise ValueError('The frozen viewer source requires its sibling sdk/rknn_api.h')
                blobs['sdk/rknn_api.h'] = sdk.read_bytes()
            if 'src/detview.pro' not in blobs or 'src/hardware_inference.h' not in blobs:
                raise ValueError('A complete prepared native-I/O viewer source tree is required')
            if args.backend == 'viewer':
                blobs['build_viewer_target.py'] = (TASK / 'build_viewer_target.py').read_bytes()
            else:
                for name in ('parity_probe.cpp', 'run_parity_target.py'):
                    blobs[name] = (TASK / 'viewer' / name).read_bytes()
                suite = TASK / 'rknn_io/prepared'
                blobs['fixture_suite/manifest.json'] = (suite / 'manifest.json').read_bytes()
                for fixture in json.loads(blobs['fixture_suite/manifest.json'])['fixtures']:
                    blobs['fixture_suite/' + fixture['path']] = (suite / fixture['path']).read_bytes()
        if args.backend == 'dma_export':
            if 'src/Makefile' not in blobs or 'src/pango_dma_candidate.c' not in blobs:
                raise ValueError('Complete DMA-exporter candidate source tree required')
            blobs['build_dma_export_target.py'] = (TASK / 'build_dma_export_target.py').read_bytes()
        request['package'] = remote + '/package'
        request['source_sha256'] = {name: hashlib.sha256(data).hexdigest() for name, data in blobs.items()}
        for name, data in blobs.items():
            local_source = directory/'frozen_source'/name
            local_source.parent.mkdir(parents=True, exist_ok=True)
            local_source.write_bytes(data)
    else:
        build = json.loads(args.build_receipt.read_text())
        if build['status'] != 'success' or build['phase'] != 'build' or build['host'] != board_host():
            raise ValueError('Successful same-board build receipt required')
        request.update({name: build[name] for name in ('package', 'source_sha256', 'binary', 'binary_sha256', 'library_sha256')})
        receipt['build_receipt_sha256'] = sha(args.build_receipt)
    receipt.update(package=request['package'], source_sha256=request['source_sha256'])
    lock = ROOT / 'log/100h_motion/board_session.lock'
    held = False
    client = None
    sent = False
    def event(value):
        receipt['events'].append(value)
        motion.viewer.atomic_json(receipt_path, receipt)
        detail = ''
        if value['state'] == 'probe_progress':
            latest = value.get('latest', '')
            elapsed = format(value.get('elapsed_seconds', 0), '.1f') + 's'
            if latest.startswith('{"event": "target",'):
                detail = 'target identity recorded; ' + value['phase'] + ' elapsed=' + elapsed
            else:
                detail = latest + ' elapsed=' + elapsed
        elif value['state'] == 'artifact_download_progress':
            detail = str(value['completed']) + '/' + str(value['total']) + ' files hash-verified'
        elif value['state'] == 'experiment_result':
            detail = value['status'] + ' certifications=' + str(value['certifications']) + ' comparisons=' + str(value['comparisons'])
            if value['declined_reasons']:
                detail += ' reason=' + ' | '.join(value['declined_reasons'])
        elif value['state'] == 'restoration_held':
            detail = value['reason'] + '; board lock retained'
        elif value['state'] == 'import_retirement_checked':
            detail = str(value['checked_logs']) + ' logs; ' + value['reason']
        print(args.backend.upper() + ': ' + value['state'] + (' ' + detail if detail else ''), flush=True)
    try:
        with lock.open('x') as stream:
            json.dump(dict(operation=token, pid=os.getpid(), action='hardware_rknn'), stream)
        held = True
        client = ssh_connect()
        _, stdout, stderr = client.exec_command('test ! -e ' + shlex.quote(remote) + ' && mkdir -p ' + shlex.quote(remote), timeout=20)
        if stdout.channel.recv_exit_status():
            raise RuntimeError('Private remote directory creation failed')
        with client.open_sftp() as transfer:
            made = {remote}
            for name, data in blobs.items():
                target = request['package'] + '/' + name
                parts = target[len(remote) + 1:].split('/')[:-1]
                parent = remote
                for component in parts:
                    parent += '/' + component
                    if parent not in made:
                        transfer.mkdir(parent)
                        made.add(parent)
                with transfer.open(target, 'wb') as stream:
                    stream.write(data)
        motion.REMOTE_SOURCE = motion.REMOTE_SOURCE.split("if __name__ == '__main__':", 1)[0] + REMOTE
        receipt['supervisor_source_sha256'] = hashlib.sha256(motion.REMOTE_SOURCE.encode()).hexdigest()
        motion.viewer.atomic_json(receipt_path, receipt)
        sent = True
        motion.remote_run(client, request, event)
        snapshots = [e for e in receipt['events'] if e['state'] == 'snapshot_saved']
        receipt['library_sha256'] = snapshots[-1]['library_sha256']
        if args.phase == 'build':
            with client.open_sftp() as transfer:
                with transfer.open(remote + '/run/results/build_receipt.json') as stream:
                    build_proof = json.load(stream)
            if args.backend == 'dma_export':
                receipt['binary'] = build_proof['module_path']
                receipt['binary_sha256'] = build_proof['module_sha256']
                if build_proof['status'] != 'private_module_compiled_no_load_or_hardware_validation':
                    raise RuntimeError('DMA-exporter private build proof incomplete')
            else:
                receipt['binary'] = remote + '/run/results/' + ('detview' if args.backend == 'viewer' else 'rknn_io_bench')
                receipt['binary_sha256'] = build_proof['executable_sha256']
            receipt['build_proof'] = build_proof
        receipt['status'] = 'success'
    except Exception as exc:
        receipt.update(status='failed', error=type(exc).__name__ + ': ' + str(exc))
        print(receipt['error'], flush=True)
    finally:
        if client is not None:
            try:
                bundles = [e for e in receipt['events'] if e['state'] == 'artifacts']
                if bundles:
                    artifact_files = bundles[-1]['files']
                    for index, artifact in enumerate(artifact_files, 1):
                        local = directory / 'artifacts' / artifact['name']
                        local.parent.mkdir(parents=True, exist_ok=True)
                        with local.open('xb') as stream:
                            def downloaded(value):
                                if value['state'] == 'artifact_chunk':
                                    stream.write(base64.b64decode(value['base64'], validate=True))
                                elif value['state'] != 'downloaded':
                                    event(value)
                            motion.remote_run(client, dict(action='download', artifact=artifact, timeout=90), downloaded)
                        if sha(local) != artifact['sha256'] or local.stat().st_size != artifact['bytes']:
                            raise RuntimeError('Private downloaded artifact hash/size differs')
                        if index % 16 == 0 or index == len(artifact_files):
                            event(dict(state='artifact_download_progress', completed=index, total=len(artifact_files)))
                    receipt['artifact_hashes_verified'] = True
                    if args.backend == 'rknn' and args.phase == 'experiment':
                        proof_path = directory/'artifacts/results/report.json'
                        proof = json.loads(proof_path.read_text())
                        receipt['experiment_report_sha256'] = sha(proof_path)
                        receipt['experiment_status'] = proof['status']
                        event(dict(state='experiment_result', status=proof['status'],
                                   certifications=len(proof.get('certifications', [])),
                                   comparisons=len(proof.get('comparisons', [])),
                                   declined_reasons=[reason for row in proof.get('unsupported', [])
                                                     for reason in row.get('reasons', [])]))
                    if args.backend == 'viewer_parity':
                        parity = json.loads((directory/'artifacts/results/parity_receipt.json').read_text())
                        if not parity.get('hardware_parity_complete'):
                            raise RuntimeError('Actual viewer helper parity failed')
                        receipt['helper_proof'] = parity
                else:
                    with client.open_sftp() as transfer:
                        def download(remote_path, local_path):
                            local_path.mkdir(exist_ok=True, parents=True)
                            for entry in transfer.listdir_attr(remote_path):
                                import stat
                                source, target = remote_path + '/' + entry.filename, local_path / entry.filename
                                if stat.S_ISDIR(entry.st_mode):
                                    download(source, target)
                                elif entry.filename.endswith(('.json', '.jsonl', '.stdout', '.stderr', '.maps', '.f32', '.u8', '.bin', '.cmd', '.ko')):
                                    transfer.get(source, str(target))
                        download(remote + '/run', directory / 'artifacts')
                    if receipt['status'] == 'success':
                        raise RuntimeError('Successful run did not retain a verified artifact manifest')
            except Exception as exc:
                receipt['artifact_download_error'] = str(exc)
                receipt['status'] = 'failed'
            client.close()
        safe = not sent or any(e['state'] in ('restored', 'viewer_preserved') for e in receipt['events'])
        receipt['board_lock_retained'] = held and not safe
        motion.viewer.atomic_json(receipt_path, receipt)
        if held and safe:
            lock.unlink()
        print('Receipt: ' + str(receipt_path), flush=True)
    return 0 if receipt['status'] == 'success' else 1


if __name__ == '__main__':
    sys.exit(main())
