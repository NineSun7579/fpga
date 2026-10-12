"""Run one bounded, receipt-pinned host stall trial and always restore HDMI.

Parent invocation AFTER build and self-tests have passed:
  python -B project/per_camera_fps/host_stall/run_diagnostic.py --build-receipt <build_host.py-receipt.json> --seconds 120 --restore
If timing is a separate executable, supply --selftest-receipt PATH or embed
selftest_proof in the build receipt. Proof schema: binary_sha256; tests with
option, exit_code=0, output_sha256 for the viewer's no-DMA startup options;
timing with exit_code=0, output_sha256, binary_sha256, source_sha256 (including
stall_timing.h at the same SHA as this build and stall_timing_selftest.cpp),
machine="aarch64". The parent
executes/builds the standalone timing test; this runner never compiles it.
Local preparation checks (no SSH): --self-test, or --build-receipt PATH --check.
--restore is the default and cannot be disabled. Runtime is never started by
--check or --self-test. The parent must exclusively own the board for execution.

The retained calibration capture supplies exact argv/cwd/credentials and its
full environment, loaded ONLY from the root-owned 0600 board snapshot. No
environment is copied into local receipts or printed. The HDMI process gets
its own fresh private snapshot and is restored using that snapshot. No FPGA,
driver, governor, scheduling, persistent environment or calibration writes.
Only WM_DELETE_WINDOW closes viewers; there are no viewer-directed signals.
If normal closure or identity validation prevents safe restoration, a failed
receipt identifies the retained private recovery snapshot; no second DMA
owner is started. An unverified restoration retains the local board-session
lock for review. Transport failure does not bypass the remote finally block.

Artifacts/analysis live in host_stall/runs/diagnostic_<unique operation>/.
The complete viewer log is retained on the board; the downloaded copy redacts
secret environment values. Proc samples never contain environ or cmdline.
Tracefs uses only a new owned instance, caps output at 1 MiB and is optional.
Full executable/config hashes and sole-owner/interference checks bracket the
measurement. Each sample checks process identity and live/disk executable
metadata; global owner/interference scans also run every 10 seconds. These are
sampled checks, not proof against a change that occurs and reverts between them.
Observer CPU/wall costs and the endpoint before final verification are retained.
The parser reads logging formats from the immutable new header(s), preserves
every matching record and numeric field, and refuses invented timing units.
"""

import argparse
import base64
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
LOG = ROOT / 'log/100h_motion'
CAL_CAPTURE = LOG / 'pll56_optimized_1182d414dcc7436f841bb2170ae93960/capture.json'
ORIGINAL_MAIN = 'd3a38d77338168b6d95a8731efe99e7b443f08b0dee7bcc831d33bc544a0fd23'
ORIGINAL_BINARY = '0d717a430e46e13d61553bf74c5ea7f13aff5c69db8587136aa227b5705ad153'
HDMI = dict(pid=109952, starttime='20587144',
            exe='/userdata/detview-hdmifull/detview-hdmifull',
            exe_sha256='0301f6901330ff161b76f1fb343edb5f0acbf93064b04794c98147da6e92a737',
            argv=['/userdata/detview-hdmifull/detview-hdmifull', '--model', 'wb_v4_combo',
                  '--fullscreen', '--no-tracking', '--prefer-hdmifull', 'auto'])
CAL_ARGV = ['/userdata/linaro/detview-calibration-work/build/detview', '--model',
            'wb_v4_combo', '--fullscreen', '--no-tracking', '--stereo-config',
            '/userdata/linaro/detview-calibration-session/trial-meters/stereo_pairs_trial.json',
            '--stereo-trial-meters', '--stereo-scale', '0.5', '--stereo-interval-ms', '250']


def sha_file(path):
    with Path(path).open('rb') as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load_helpers():
    spec = importlib.util.spec_from_file_location(
        'host_stall_motion_helpers', ROOT / 'project/motion_scheduling/board_viewer.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def logging_formats(text):
    # Adjacent C string literals are joined before extracting the actual tags.
    literals = re.findall(r'(?:"(?:\\.|[^"\\])*"\s*)+', text)
    result = []
    for group in literals:
        pieces = re.findall(r'"((?:\\.|[^"\\])*)"', group)
        value = ''.join(pieces).replace('\\n', '\n')
        if re.search(r'\[[A-Za-z][A-Za-z0-9_.:-]*\]', value) and '%' in value:
            result.append(value)
    return result


def validate_build(path, motion):
    build = motion.validate_build(read_json(path))
    source = Path(build['source'])
    actual = {p.relative_to(source).as_posix(): sha_file(p)
              for p in source.rglob('*') if p.is_file()}
    if actual != build['source_sha256']:
        raise ValueError('Frozen local build inputs differ from build receipt')
    provenance = read_json(HERE / 'board_provenance_readonly.json')
    prefix = '/userdata/linaro/detview-calibration-work/src/'
    retained = {f['path'][len(prefix):]: f['sha256'] for f in provenance['files']
                if f['path'].startswith(prefix) and not f['path'].endswith('stereo_pairs.example.json')}
    if retained.get('main.cpp') != ORIGINAL_MAIN:
        raise ValueError('Retained original main.cpp identity mismatch')
    for name, digest in retained.items():
        if name != 'main.cpp' and actual.get(name) != digest:
            raise ValueError('Existing source changed outside main.cpp: ' + name)
    if actual.get('main.cpp') in (None, ORIGINAL_MAIN):
        raise ValueError('Instrumented main.cpp required')
    sdk = next(f['sha256'] for f in provenance['files']
               if f['path'] == '/userdata/linaro/detview-calibration-work/sdk/rknn_api.h')
    if actual.get('rknn_api.h') != sdk:
        raise ValueError('Retained SDK header changed')
    additions = sorted(set(actual) - set(retained) - {'rknn_api.h'})
    if additions != ['stall_timing.h']:
        raise ValueError('Only new stall_timing.h may accompany modified main.cpp')
    formats = {name: logging_formats((source / name).read_text(encoding='utf-8-sig'))
               for name in additions}
    if not any(formats.values()):
        raise ValueError('Cannot identify logging format in immutable diagnostic header')
    main = (source / 'main.cpp').read_text(encoding='utf-8-sig')
    options = sorted(set(re.findall(r'"(--[a-z0-9-]*selftest)"', main)))
    timing = [option for option in options if re.search(r'timing|host-stall|diagnostic', option)]
    if len(timing) > 1:
        raise ValueError('Ambiguous no-DMA timing diagnostic self-test options')
    tests = ['--vision-selftest', '--camera-dma-selftest'] + timing
    if any(option not in options for option in tests):
        raise ValueError('Required no-DMA self-test option missing from frozen source')
    return build, formats, tests


def validate_proof(proof, build, tests, motion):
    if proof:
        if (proof.get('binary_sha256') != build['binary_sha256'] or
                {t['option'] for t in proof.get('tests', [])} != set(tests) or
                any(t.get('exit_code') != 0 or not re.fullmatch('[0-9a-f]{64}', str(t.get('output_sha256', '')))
                    for t in proof.get('tests', []))):
            raise ValueError('Self-test evidence must pin this binary and all passed no-DMA options')
    if len(tests) == 2:
        timing = proof.get('timing', {}) if proof else {}
        headers = {name: digest for name, digest in build['source_sha256'].items()
                   if Path(name).name == 'stall_timing.h'}
        if (not headers or timing.get('exit_code') != 0 or timing.get('machine') != 'aarch64' or
                any(timing.get('source_sha256', {}).get(name) != digest for name, digest in headers.items())):
            raise ValueError('Standalone target timing self-test proof with this header SHA is required')
        source_hash = sha_file(HERE / 'diagnostic/stall_timing_selftest.cpp')
        if timing.get('source_sha256', {}).get('stall_timing_selftest.cpp') != source_hash:
            raise ValueError('Standalone timing test source differs from retained diagnostic self-test')
        motion.valid_hash(timing.get('binary_sha256'))
        motion.valid_hash(timing.get('output_sha256'))
    return proof


def calibration_request(path, motion):
    capture = read_json(path)
    if capture.get('status') != 'success' or capture.get('action') != 'identity_snapshot':
        raise ValueError('Successful retained calibration capture required')
    snapshots = [e for e in capture['events'] if e.get('state') == 'snapshot_saved']
    targets = [e for e in capture['events'] if e.get('state') == 'started']
    if len(snapshots) != 1 or len(targets) != 1 or targets[0]['exe_sha256'] != ORIGINAL_BINARY:
        raise ValueError('Original calibration capture identity mismatch')
    snapshot = snapshots[0]
    if snapshot.get('preserved_argv') != CAL_ARGV:
        raise ValueError('Retained original calibration argv differs')
    operation = capture['operation']
    if not re.fullmatch('[0-9a-f]{32}', operation):
        raise ValueError('Invalid calibration operation')
    expected = '/userdata/linaro/100h_performance/motion_viewer_' + operation + '.snapshot.json'
    if snapshot['snapshot'] != expected:
        raise ValueError('Calibration private snapshot path mismatch')
    motion.valid_hash(snapshot['snapshot_sha256'])
    for name, digest in snapshot['files'].items():
        if not name.startswith('/') or '\0' in name:
            raise ValueError('Invalid calibration asset path')
        motion.valid_hash(digest)
    return dict(path=expected, sha256=snapshot['snapshot_sha256'], operation=operation,
                files=snapshot['files'], argv=CAL_ARGV, host=capture['host'])


REMOTE_AGENT = r'''
import base64
import errno

MAX_LOG = 128 * 1024 * 1024
MAX_TRACE = 1024 * 1024
PROC_ROOT = Path('/proc')
SAMPLE_PERIOD_NS = 1000000000
GLOBAL_GUARD_PERIOD_NS = 10000000000
ASSET_SUFFIXES = {'.json', '.yaml', '.yml', '.xml', '.ini', '.cfg', '.npz', '.npy', '.rknn'}
CAL_ROOTS = ['/userdata/linaro/detview-calibration-session',
             '/userdata/linaro/detview-calibration-work/src']

def text(path):
    try:
        return Path(path).read_text().strip()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None

def clocks():
    value = dict(monotonic_ns=time.clock_gettime_ns(time.CLOCK_MONOTONIC),
                 raw_ns=time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW),
                 boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME), realtime_ns=time.time_ns(),
                 sampler_cpu_ns=time.thread_time_ns())
    class Timespec(C.Structure):
        _fields_ = [('sec', C.c_long), ('nsec', C.c_long)]
    if os.uname().machine == 'aarch64':
        result = Timespec()
        rc = C.CDLL(None).syscall(C.c_long(113), C.c_int(1), C.byref(result))
        value['syscall_monotonic_ns'] = result.sec * 1000000000 + result.nsec if rc == 0 else None
    return value

def paired_time():
    return dict(monotonic_ns=time.monotonic_ns(), sampler_cpu_ns=time.thread_time_ns())

def paired_cost(begin, end):
    return dict(wall_ns=end['monotonic_ns'] - begin['monotonic_ns'],
                cpu_ns=end['sampler_cpu_ns'] - begin['sampler_cpu_ns'])

def executable_metadata(path):
    info = os.stat(path)
    require(stat.S_ISREG(info.st_mode), 'Diagnostic executable is not a regular file')
    return dict(dev=info.st_dev, ino=info.st_ino, size=info.st_size,
                mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns)

def sample_identity(common, pinned=None):
    # No hashing or all-process walks. Check both the running inode and disk
    # inode against the metadata captured around the initial full SHA check.
    config, baseline, target = common['config'], common['baseline'], common['target']
    root = PROC_ROOT / str(target['pid'])
    def live_stat():
        raw = (root / 'stat').read_text()
        fields = raw[raw.rfind(')') + 2:].split()
        require(int(raw.split(' ', 1)[0]) == target['pid'] and fields[19] == target['starttime'] and
                fields[0] != 'Z', 'Diagnostic PID exited/reused during identity check')
    live_stat()
    exe = os.readlink(root / 'exe')
    require(exe == config['exe'] and os.path.realpath(exe) == config['exe'],
            'Diagnostic executable path changed')
    live = executable_metadata(root / 'exe')
    disk = executable_metadata(config['exe'])
    require(live == disk, 'Diagnostic live/disk executable metadata differ')
    status = (root / 'status').read_text()
    uids = [int(v) for v in re.search(r'^Uid:[ \t]*(.*)$', status, re.M)[1].split()]
    gids = [int(v) for v in re.search(r'^Gid:[ \t]*(.*)$', status, re.M)[1].split()]
    groups = [int(v) for v in re.search(r'^Groups:[ \t]*(.*)$', status, re.M)[1].split()]
    require(len(uids) == len(gids) == 4 and uids[0] == baseline['uid'] and gids[0] == baseline['gid'] and
            groups == baseline['groups'], 'Diagnostic credentials changed')
    argv = [os.fsdecode(v) for v in (root / 'cmdline').read_bytes().split(b'\0') if v]
    require(argv == config['argv'], 'Diagnostic argv changed')
    require(os.readlink(root / 'cwd') == config['cwd'], 'Diagnostic cwd changed')
    environment = {}
    for item in (root / 'environ').read_bytes().split(b'\0'):
        if item:
            key, value = item.split(b'=', 1)
            environment[os.fsdecode(key)] = os.fsdecode(value)
    require(environment == config['env'], 'Diagnostic full environment changed')
    require(boot() == baseline['boot_id'], 'Board rebooted during observation')
    identity = dict(exe_metadata=live, uids=uids, gids=gids)
    require(pinned is None or identity == pinned, 'Diagnostic sampled identity metadata changed')
    require(executable_metadata(root / 'exe') == live and executable_metadata(config['exe']) == disk,
            'Diagnostic executable metadata changed during identity read')
    live_stat()  # Refuse an exit/reuse during the reads as well as before them.
    return identity  # Never persist environ/cmdline contents in proc samples.

def pin_sample_identity(common):
    before = sample_identity(common)
    exact(common)  # SHA the current live executable; do not substitute disk SHA.
    sample_identity(common, before)
    return before

def target_owns_dma(target):
    # A target-only descriptor/map walk between the global sole-owner guards.
    device = os.stat(DEVICE)
    require(stat.S_ISCHR(device.st_mode), 'DMA device absent/not a character device')
    root = PROC_ROOT / str(target['pid'])
    for fd in (root / 'fd').iterdir():
        try:
            info = fd.stat()
        except FileNotFoundError:
            continue
        if stat.S_ISCHR(info.st_mode) and info.st_rdev == device.st_rdev:
            return True
    for line in (root / 'maps').read_text().splitlines():
        fields = line.split(None, 5)
        major, minor = (int(v, 16) for v in fields[3].split(':'))
        if (major, minor, int(fields[4])) == (os.major(device.st_dev), os.minor(device.st_dev), device.st_ino):
            return True
    return False

def global_observation_guard(target):
    require(owners() == [target['pid']], 'Diagnostic is not sole DMA owner')
    measurement_quiescent()

def trace_loss_summary(stats, truncated):
    counts = dict(overrun=0, commit_overrun=0, dropped_events=0)
    known = bool(stats)
    for value in stats.values():
        for label, key in [('overrun', 'overrun'), ('commit overrun', 'commit_overrun'),
                           ('dropped events', 'dropped_events')]:
            match = re.search(r'^' + label + r':\s*(\d+)\s*$', value or '', re.M)
            known = known and match is not None
            if match:
                counts[key] += int(match[1])
    warnings = []
    if truncated:
        warnings.append('Trace reached its byte ceiling; later events were not retained.')
    if any(counts.values()):
        warnings.append('Trace per-CPU counters report lost/overwritten events.')
    if not known:
        warnings.append('Trace loss counters unavailable or incomplete.')
    return dict(loss_counters=counts, loss_counters_complete=known, warnings=warnings,
                scheduler_absence_interpretation='Unknown: filtered, sampled-TID, bounded trace cannot exclude scheduler activity.')

def pin_files(snap, prior):
    # Previously recorded pins are compared, never replaced with newer hashes.
    for path, digest in prior.items():
        require(Path(path).is_file() and sha(path) == digest, 'Previously pinned file changed: ' + path)
    pins = dict(prior)
    relative = {}
    pending = []
    for arg in snap['argv'][1:]:
        path = Path(arg) if arg.startswith('/') else Path(snap['cwd']) / arg
        if path.is_file():
            path = str(path.resolve())
            pending.append(path)
            if not arg.startswith('/'):
                relative[arg] = path
    for root in CAL_ROOTS:
        if Path(root).is_dir():
            pending += [str(p) for p in Path(root).rglob('*')
                        if p.is_file() and p.suffix.lower() in ASSET_SUFFIXES]
    visited = set()
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        digest = sha(path)
        require(path not in pins or pins[path] == digest, 'Asset changed during capture: ' + path)
        pins[path] = digest
        if Path(path).suffix.lower() not in {'.json', '.yaml', '.yml', '.xml', '.ini', '.cfg'}:
            continue
        # JSON string values and plain YAML/OpenCV path scalars; no config contents emitted.
        data = Path(path).read_text(errors='replace')
        candidates = re.findall(r'[^\s\"\'<>\[\]{},:]+\.(?:json|ya?ml|xml|ini|cfg|npz|npy|rknn)', data)
        if Path(path).suffix.lower() == '.json':
            try:
                todo = [json.loads(data)]
                while todo:
                    item = todo.pop()
                    if isinstance(item, dict):
                        todo.extend(item.values())
                    elif isinstance(item, list):
                        todo.extend(item)
                    elif isinstance(item, str) and Path(item).suffix.lower() in ASSET_SUFFIXES:
                        candidates.append(item)
            except ValueError:
                pass  # Non-JSON content is still pinned byte-for-byte.
        for reference in candidates:
            choices = [Path(reference)] if reference.startswith('/') else [Path(path).parent / reference,
                                                                         Path(snap['cwd']) / reference]
            for choice in choices:
                if choice.is_file():
                    resolved = str(choice.resolve())
                    pending.append(resolved)
                    relative[path + ':' + reference] = resolved
                    break
    pins[snap['exe']] = sha(snap['exe'])
    return pins, relative

def check_current(expected, prior):
    require(owners() == [expected['pid']], 'Expected HDMI PID is not sole DMA owner')
    snap = process(expected['pid'])
    require(snap is not None, 'Expected HDMI process absent')
    for key in ('pid', 'starttime', 'exe', 'exe_sha256', 'argv'):
        require(snap[key] == expected[key], 'Current HDMI identity changed: ' + key)
    require(snap['uid'] == 0 and not snap['environment'].get('LD_PRELOAD'), 'Unexpected current credentials/preload')
    snap['files'], snap['relative_files'] = pin_files(snap, prior)
    config = config_for(snap, '')
    exact(dict(config=config, baseline=snap, target=snap))
    win = windows(snap['pid'], snap['environment'])
    require(len(win) == 1 and win[0]['delete_supported'], 'HDMI requires unique normal-close window')
    require(owners() == [snap['pid']], 'Current DMA owner changed during capture')
    snap['windows'] = win
    return snap

def load_calibration(request):
    cal = request['calibration']
    require(sha(cal['path']) == cal['sha256'], 'Retained calibration snapshot hash changed')
    saved = private_read(cal['path'])
    require(saved['operation'] == cal['operation'] and saved['boot_id'] == boot(), 'Calibration snapshot operation/boot mismatch')
    old = saved['baseline']
    require(old['exe_sha256'] == request['original_binary'] and old['argv'] == cal['argv'], 'Private calibration identity/argv mismatch')
    require(old['files'] == cal['files'], 'Private calibration file pins differ from retained receipt')
    require(saved['config']['env'] == old['environment'], 'Incomplete saved calibration environment')
    require(old['cwd'] == '/userdata/linaro/detview-calibration-work/build', 'Calibration cwd changed')
    require(old['uid'] == 0 and old['gid'] >= 0 and isinstance(old['groups'], list), 'Calibration credentials missing')
    env = old['environment']
    require(env.get('QT_QPA_PLATFORM') == 'xcb' and env.get('DISPLAY') and
            env.get('XAUTHORITY', '').startswith('/'), 'Retained X11 environment missing')
    require(not env.get('LD_PRELOAD'), 'Unexpected retained preload')
    require(env.get('DETVIEW_SWAP_INTERVAL') == '0' and env.get('DETVIEW_TEXTURE_RING') == '1',
            'Retained calibration swap/ring differ from original diagnostic baseline')
    verify_files(saved['config'], old)
    old['files'], old['relative_files'] = pin_files(old, cal['files'])
    return old

def check_build(build):
    require(re.fullmatch('/userdata/linaro/100h_performance/build_[0-9a-f]{16}/build/detview', build['binary']),
            'Invalid immutable diagnostic executable path')
    require(os.path.realpath(build['binary']) == build['binary'], 'Diagnostic path contains symlink')
    require(sha(build['binary']) == build['binary_sha256'], 'Diagnostic binary SHA256 mismatch')
    for name, digest in build['source_sha256'].items():
        require(sha(build['remote_directory'] + '/src/' + name) == digest, 'Immutable source changed: ' + name)

def secret_values(*environments):
    return sorted({value for env in environments for key, value in env.items()
                   if value and re.search(r'PASS|TOKEN|SECRET|CREDENTIAL|COOKIE|(?:^|_)KEY(?:$|_)', key, re.I)},
                  key=len, reverse=True)

def redact(data, secrets):
    for value in secrets:
        data = data.replace(value, '<redacted>')
    return data

def no_dma_tests(request, config, emit):
    proof = request.get('selftest_proof')
    if proof:
        require(proof['binary_sha256'] == request['build']['binary_sha256'], 'Self-test proof binary mismatch')
        require({t['option'] for t in proof['tests']} == set(request['test_options']) and
                all(t['exit_code'] == 0 and re.fullmatch('[0-9a-f]{64}', t['output_sha256']) for t in proof['tests']),
                'Incomplete successful self-test proof')
        emit('selftests_verified', reused=True, options=request['test_options'])
        if len(request['test_options']) == 2:
            timing = proof['timing']
            require(timing['exit_code'] == 0 and timing['machine'] == 'aarch64' and
                    all(timing['source_sha256'].get(name) == digest for name, digest in
                        request['build']['source_sha256'].items() if Path(name).name == 'stall_timing.h'),
                    'Standalone target timing self-test proof/header mismatch')
            emit('timing_selftest_verified', binary_sha256=timing['binary_sha256'],
                 output_sha256=timing['output_sha256'])
        return
    env = dict(config['env'], QT_QPA_PLATFORM='offscreen')
    for option in request['test_options']:
        result = subprocess.run([config['exe'], option], cwd=config['cwd'], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=40)
        emit('selftest', option=option, exit_code=result.returncode,
             output_sha256=hashlib.sha256(result.stdout).hexdigest(), output_bytes=len(result.stdout))
        require(result.returncode == 0, 'No-DMA self-test failed: ' + option)
    emit('selftests_verified', reused=False, options=request['test_options'])

class Trace:
    def __init__(self, operation, enabled, output):
        self.path = None
        self.fd = None
        self.output = output
        self.bytes = 0
        self.tids = []
        self.last_drain_ns = None
        self.meta = dict(requested=enabled, active=False, byte_limit=MAX_TRACE,
                         buffer_per_cpu_kb=64, nominal_drain_period_seconds=SAMPLE_PERIOD_NS / 1e9,
                         drain_calls=0, max_drain_gap_ns=0, filters_cover='sampled viewer TIDs only',
                         scheduler_absence_interpretation='Unknown: filtered, sampled-TID, bounded trace cannot exclude scheduler activity.')
        if not enabled:
            return
        roots = [Path('/sys/kernel/tracing'), Path('/sys/kernel/debug/tracing')]
        base = next((p for p in roots if (p / 'instances').is_dir()), None)
        if base is None:
            self.meta['reason'] = 'tracefs instances unavailable'
            return
        try:
            path = base / 'instances' / ('host_stall_' + operation)
            path.mkdir()  # Exclusive; never adopts an existing instance.
            self.path = path
            info = path.stat()
            self.identity = (info.st_dev, info.st_ino, info.st_uid)
            require(info.st_uid == 0, 'Trace instance not root-owned')
            self.write('tracing_on', '0')
            self.write('current_tracer', 'nop')
            self.write('buffer_size_kb', '64')
            if 'mono' in (path / 'trace_clock').read_text().replace('[', '').replace(']', '').split():
                self.write('trace_clock', 'mono')
            self.meta['clock'] = (path / 'trace_clock').read_text().strip()
            self.events = []
            for event, fields in [('sched/sched_switch', ['prev_pid', 'next_pid']),
                                  ('signal/signal_generate', ['sig', 'pid'])]:
                target = path / 'events' / event
                if target.is_dir() and all(re.search(r'\b' + key + r'\s*;', (target / 'format').read_text()) for key in fields):
                    self.events.append(event)
            require('sched/sched_switch' in self.events, 'Filtered instance scheduler event unavailable')
            self.fd = os.open(path / 'trace_pipe', os.O_RDONLY | os.O_NONBLOCK)
            self.meta['instance'] = str(path)
        except BaseException as exc:
            self.meta['reason'] = type(exc).__name__ + ': ' + str(exc)
            self.close()

    def owned(self):
        info = self.path.stat()
        require((info.st_dev, info.st_ino, info.st_uid) == self.identity, 'Trace instance ownership changed')

    def write(self, name, value):
        self.owned()
        (self.path / name).write_text(value)

    def update(self, tids):
        if self.path is None or self.bytes >= MAX_TRACE or tids == self.tids:
            return
        require(tids and all(type(tid) is int and tid > 0 for tid in tids), 'Invalid trace viewer TIDs')
        self.write('tracing_on', '0')
        for event in self.events:
            if event == 'sched/sched_switch':
                expression = ' || '.join('(prev_pid == %d || next_pid == %d)' % (tid, tid) for tid in tids)
            else:
                expression = '(sig == 19 || sig == 18) && (' + ' || '.join('pid == %d' % tid for tid in tids) + ')'
            self.write('events/' + event + '/filter', expression)
            self.write('events/' + event + '/enable', '1')
        self.tids = list(tids)
        self.write('tracing_on', '1')
        self.meta.update(active=True, events=self.events, last_tids=self.tids)

    def drain(self):
        if self.fd is None or self.bytes >= MAX_TRACE:
            return
        now = time.monotonic_ns()
        self.meta['drain_calls'] += 1
        if self.last_drain_ns is not None:
            self.meta['max_drain_gap_ns'] = max(self.meta['max_drain_gap_ns'], now - self.last_drain_ns)
        self.last_drain_ns = now
        while self.bytes < MAX_TRACE:
            try:
                block = os.read(self.fd, min(65536, MAX_TRACE - self.bytes))
            except BlockingIOError:
                break
            if not block:
                break
            self.output.write(block)
            self.bytes += len(block)
        if self.bytes >= MAX_TRACE and self.path is not None:
            self.meta['truncated'] = True
            self.stop()

    def stop(self):
        if self.path is not None:
            self.write('tracing_on', '0')
            if 'stopped_at' not in self.meta:
                self.meta['stopped_at'] = clocks()

    def close(self):
        if self.path is None:
            return
        path = self.path
        try:
            self.stop()
            for event in getattr(self, 'events', []):
                self.write('events/' + event + '/enable', '0')
            self.drain()
            self.meta['per_cpu_stats'] = {str(p.relative_to(path)): text(p)
                                          for p in path.glob('per_cpu/cpu*/stats')}
            self.meta.update(trace_loss_summary(self.meta['per_cpu_stats'], self.meta.get('truncated', False)))
        finally:
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
            self.owned()
            path.rmdir()  # Kernel removes only this instance's virtual entries.
            self.path = None
            self.meta.update(cleaned=True, bytes=self.bytes)

def proc_sample(target, index):
    read_begin = clocks()
    root = PROC_ROOT / str(target['pid'])
    raw = (root / 'stat').read_text()
    fields = raw[raw.rfind(')') + 2:].split()
    require(fields[19] == target['starttime'] and fields[0] != 'Z', 'Diagnostic PID exited/reused during sample')
    threads = []
    for task in sorted((root / 'task').iterdir(), key=lambda p: int(p.name)):
        task_begin = time.monotonic_ns()
        value = text(task / 'stat')
        if value is None:
            continue
        entry = value[value.rfind(')') + 2:].split()
        threads.append(dict(tid=int(task.name), starttime=entry[19], state=entry[0],
                            cpu_ticks=int(entry[11]) + int(entry[12]), stat=value,
                            status=text(task / 'status'), schedstat=text(task / 'schedstat'),
                            wchan=text(task / 'wchan'),
                            stack=text(task / 'stack') if entry[0] in ('D', 'T', 't') else None,
                            read_begin_ns=task_begin, read_end_ns=time.monotonic_ns()))
    freqs = list(Path('/sys/class/devfreq').glob('*/cur_freq'))
    freqs += list(Path('/sys/devices/system/cpu/cpufreq').glob('policy*/scaling_cur_freq'))
    sample = dict(kind='sample', index=index, clocks=clocks(), read_begin_clocks=read_begin,
                pid=target['pid'], starttime=target['starttime'],
                hz=os.sysconf('SC_CLK_TCK'), process_stat=raw, threads=threads,
                schedstats_enabled=text('/proc/sys/kernel/sched_schedstats'),
                proc_stat=text('/proc/stat'), interrupts=text('/proc/interrupts'),
                loadavg=text('/proc/loadavg'), frequencies={str(p): text(p) for p in freqs},
                clocksource=text('/sys/devices/system/clocksource/clocksource0/current_clocksource'))
    sample['read_end_clocks'] = clocks()
    return sample

def observe_trial(request, saved, target, emit):
    directory = Path(request['directory'])
    trace = None
    observe_begin = paired_time()
    common = dict(config=saved['candidate_config'], baseline=saved['candidate'], target=target)
    policy = dict(sample_period_seconds=SAMPLE_PERIOD_NS / 1e9,
                  global_guard_period_seconds=GLOBAL_GUARD_PERIOD_NS / 1e9,
                  sample_checks=['PID/starttime/non-zombie', 'real executable path',
                                 'live and disk executable dev/inode/size/mtime_ns/ctime_ns',
                                 'argv/cwd/full environment/uid/gid/groups/boot', 'target DMA descriptor or map'],
                  boundary_checks=['live executable SHA256', 'disk executable/config/source SHA256',
                                   'sole DMA owner', 'interference guard'],
                  limits=['Identity metadata is validated at samples against the initial SHA-verified live/disk inode.',
                          'Global sole-owner/interference checks run at boundaries and every 10 seconds, subject to observer delays.',
                          'Changes that occur and revert between checks can be missed; global guards can miss short-lived interference.',
                          'Sample collection costs exclude JSON output; iteration/total costs include it. CPU is supervisor thread CPU.',
                          'Measured endpoint precedes final SHA/config/owner verification and trace cleanup.'])
    costs = dict(iterations=0, max_iteration_cpu_ns=0, max_iteration_wall_ns=0,
                 max_cpu_interval_ns=0, max_cpu_interval_wall_ns=0, sample_output_cpu_ns=0,
                 sample_output_wall_ns=0, global_guards=0, max_global_guard_gap_ns=0)
    measurement_begin = None
    measurement_end = None
    verification_begin = None
    verification_end = None
    last_guard_ns = None
    count = 0
    def track_interval(before, after):
        interval = paired_cost(before, after)
        if interval['cpu_ns'] > costs['max_cpu_interval_ns']:
            costs['max_cpu_interval_ns'] = interval['cpu_ns']
            costs['max_cpu_interval_wall_ns'] = interval['wall_ns']
            costs['max_cpu_interval_begin'] = before
            costs['max_cpu_interval_end'] = after
    def track_iteration(begin, end):
        work = paired_cost(begin, end)
        costs['iterations'] += 1
        costs['max_iteration_cpu_ns'] = max(costs['max_iteration_cpu_ns'], work['cpu_ns'])
        costs['max_iteration_wall_ns'] = max(costs['max_iteration_wall_ns'], work['wall_ns'])
    def guard():
        nonlocal last_guard_ns
        begin = paired_time()
        global_observation_guard(target)
        end = paired_time()
        if last_guard_ns is not None:
            costs['max_global_guard_gap_ns'] = max(costs['max_global_guard_gap_ns'], begin['monotonic_ns'] - last_guard_ns)
        last_guard_ns = begin['monotonic_ns']
        costs['global_guards'] += 1
        return dict(begin=begin, end=end, **paired_cost(begin, end))
    with open(directory / 'proc.jsonl', 'xb') as samples, open(directory / 'trace.txt', 'xb') as output:
        os.chmod(directory / 'proc.jsonl', 0o600)
        os.chmod(directory / 'trace.txt', 0o600)
        try:
            pinned = pin_sample_identity(common)
            verify_files(saved['candidate_config'], saved['candidate'])
            guard()
            sample_identity(common, pinned)
            trace = Trace(request['operation'], request['tracefs'], output)
            measurement_begin = clocks()
            deadline_ns = measurement_begin['monotonic_ns'] + request['seconds'] * 1000000000
            previous_iteration_end = measurement_begin
            emit('measurement_started', clocks=measurement_begin, seconds_limit=request['seconds'],
                 samples_limit=180, observation_policy=policy,
                 setup_observer_cost=paired_cost(observe_begin, measurement_begin))
            while count < 180 and time.monotonic_ns() < deadline_ns:
                iteration_begin = paired_time()
                identity = sample_identity(common, pinned)
                require(target_owns_dma(target), 'Diagnostic no longer holds a DMA descriptor/map')
                global_guard = None
                if iteration_begin['monotonic_ns'] - last_guard_ns >= GLOBAL_GUARD_PERIOD_NS:
                    global_guard = guard()
                if time.monotonic_ns() >= deadline_ns:
                    iteration_end = paired_time()
                    track_iteration(iteration_begin, iteration_end)
                    track_interval(previous_iteration_end, iteration_end)
                    previous_iteration_end = iteration_end
                    break  # A delayed guard must not start a proc sample after the deadline.
                sample = proc_sample(target, count)
                sample_identity(common, pinned)
                if trace.path is not None:
                    trace.update([t['tid'] for t in sample['threads']])
                    trace.drain()
                collection_end = paired_time()
                sample['observer'] = dict(collection_begin=iteration_begin, collection_end=collection_end,
                                          collection_cost=paired_cost(iteration_begin, collection_end),
                                          identity=identity, target_dma_owner_validated=True,
                                          global_guard=global_guard, last_global_guard_monotonic_ns=last_guard_ns)
                output_begin = paired_time()
                samples.write((json.dumps(sample) + '\n').encode())
                samples.flush()
                output_end = paired_time()
                output_cost = paired_cost(output_begin, output_end)
                costs['sample_output_cpu_ns'] += output_cost['cpu_ns']
                costs['sample_output_wall_ns'] += output_cost['wall_ns']
                if count % 10 == 0:
                    emit('measurement_progress', index=count, clocks=sample['clocks'])
                iteration_end = paired_time()
                track_iteration(iteration_begin, iteration_end)
                track_interval(previous_iteration_end, iteration_end)
                previous_iteration_end = iteration_end
                count += 1
                # Keep a one-second grid, skip missed slots, never catch up with
                # back-to-back samples or add a full sleep after observer work.
                now = time.monotonic_ns()
                next_sample = measurement_begin['monotonic_ns'] + (
                    (now - measurement_begin['monotonic_ns']) // SAMPLE_PERIOD_NS + 1) * SAMPLE_PERIOD_NS
                remaining_ns = min(next_sample, deadline_ns) - now
                if remaining_ns > 0:
                    time.sleep(remaining_ns / 1e9)
            measurement_end = clocks()
            track_interval(previous_iteration_end, measurement_end)
            measurement_cost = paired_cost(measurement_begin, measurement_end)
            emit('measurement_endpoint', clocks=measurement_end, samples=count,
                 elapsed_seconds=measurement_cost['wall_ns'] / 1e9, observer_cost=measurement_cost)
            verification_begin = paired_time()
            trace.stop()
            exact(common)
            sample_identity(common, pinned)
            guard()
            verify_files(saved['candidate_config'], saved['candidate'])
            sample_identity(common, pinned)
            verification_end = clocks()
            emit('measured', samples=count, clocks=measurement_end,
                 elapsed_seconds=measurement_cost['wall_ns'] / 1e9, observer_cost=measurement_cost,
                 verification_end_clocks=verification_end,
                 endpoint_verification_cost=paired_cost(verification_begin, verification_end))
        except BaseException:
            if measurement_begin is not None and measurement_end is None:
                measurement_end = clocks()
                track_interval(previous_iteration_end, measurement_end)
                emit('measurement_aborted', clocks=measurement_end, samples=count,
                     observer_cost=paired_cost(measurement_begin, measurement_end))
            if verification_begin is not None and verification_end is None:
                verification_end = paired_time()
            raise
        finally:
            try:
                if trace is not None:
                    try:
                        trace.close()
                    finally:
                        private_write(str(directory / 'trace.meta.json'), trace.meta)
                        emit('trace_finished', metadata=trace.meta)
            finally:
                samples.close()
                output.close()
                observe_end = paired_time()
                costs.update(total=paired_cost(observe_begin, observe_end),
                             begin=observe_begin, end=observe_end, samples=count,
                             setup=paired_cost(observe_begin, measurement_begin) if measurement_begin else None,
                             measurement=paired_cost(measurement_begin, measurement_end) if measurement_end else None,
                             endpoint_verification=paired_cost(verification_begin, verification_end or observe_end)
                                                   if verification_begin else None,
                             scope='observe_trial setup, measurement, endpoint verification, trace cleanup/artifact metadata and stream close; excludes viewer startup/restoration and this summary emission')
                emit('observer_finished', observer_cost=costs, observation_policy=policy)

def restore_hdmi(request, saved, target, emit):
    original = saved['original']
    config = saved['original_config']
    verify_files(config, original)
    still = process(original['pid'])
    if still is not None:
        exact(dict(config=config, baseline=original, target=original))
        require(owners() == [original['pid']], 'Saved HDMI remains with unexpected DMA owner')
        emit('restored', pid=still['pid'], starttime=still['starttime'], exe_sha256=still['exe_sha256'],
             retained_running=True)
        return
    if target is not None:
        close_exact(saved['candidate_config'], saved['candidate'], target, emit)
    require(not owners(), 'DMA still owned; cannot safely restore HDMI')
    require(not same_exe_pids(saved['candidate_config']['exe']), 'Diagnostic process still exists')
    original_action(dict(action='restore', config=config, baseline=original,
                         target=target or original, restore_log=request['directory'] + '/restored_hdmi.log',
                         timeout=40), emit)

def run_trial(request, emit):
    saved = None
    target = None
    failure = None
    restore_failure = None
    check_build(request['build'])
    old = load_calibration(request)
    original = check_current(request['current'], old['files'])
    build = request['build']
    candidate = dict(old, exe=build['binary'], exe_sha256=build['binary_sha256'],
                     argv=[build['binary']] + old['argv'][1:])
    candidate['files'] = dict(old['files'])
    candidate['files'][build['binary']] = build['binary_sha256']
    candidate['files'].update({build['remote_directory'] + '/src/' + p: h
                              for p, h in build['source_sha256'].items()})
    directory = Path(request['directory'])
    directory.mkdir(mode=0o700)
    require(directory.stat().st_uid == 0 and stat.S_IMODE(directory.stat().st_mode) == 0o700,
            'Trial directory must be private/root owned')
    candidate_config = config_for(candidate, str(directory / 'candidate.log'))
    original_config = config_for(original, str(directory / 'restored_hdmi.log'))
    saved = dict(operation=request['operation'], boot_id=boot(), original=original,
                 original_config=original_config, candidate=candidate, candidate_config=candidate_config,
                 retained_calibration_snapshot=request['calibration'])
    private_write(str(directory / 'original.snapshot.json'), saved)
    emit('snapshot_saved', snapshot=str(directory / 'original.snapshot.json'),
         snapshot_sha256=sha(directory / 'original.snapshot.json'), original_pid=original['pid'],
         original_starttime=original['starttime'], original_exe_sha256=original['exe_sha256'],
         candidate_argv=candidate['argv'], candidate_cwd=candidate['cwd'], files=candidate['files'],
         environment_sha256=hashlib.sha256(json.dumps(candidate['environment'], sort_keys=True).encode()).hexdigest())
    try:
        no_dma_tests(request, candidate_config, emit)
        verify_files(candidate_config, candidate)
        measurement_quiescent()
        close_exact(original_config, original, original, emit)
        require(not owners(), 'DMA remains owned after normal HDMI close')
        def started(state, **details):
            nonlocal target
            if state in ('launched', 'candidate_identity'):
                # Remember a launched PID even when readiness fails or it crashes.
                current = process(details['pid'])
                if current is not None:
                    target = dict(pid=current['pid'], starttime=current['starttime'], exe_sha256=build['binary_sha256'])
                    exact(dict(config=candidate_config, baseline=candidate, target=target))
                elif state == 'candidate_identity':
                    target = dict(pid=details['pid'], starttime=details['starttime'], exe_sha256=build['binary_sha256'])
                if target is not None:
                    path = str(directory / 'candidate.identity.json')
                    retained = dict(operation=request['operation'], **target)
                    if Path(path).exists():
                        require(private_read(path) == retained, 'Candidate launch identity changed')
                    else:
                        private_write(path, retained)
            emit(state, **details)
        candidate_action(dict(action='start', config=candidate_config, baseline=candidate,
                              timeout=35, ready_seconds=3, log=candidate_config['log']), started)
        require(target is not None, 'No diagnostic process identity retained')
        observe_trial(request, saved, target, emit)
    except BaseException as exc:
        failure = type(exc).__name__ + ': ' + str(exc)
        emit('trial_failed', error=failure)
    finally:
        # Recovery receives a fresh deadline even if the trial's alarm expired.
        signal.setitimer(signal.ITIMER_REAL, 100)
        try:
            emit('restoration_started')
            restore_hdmi(request, saved, target, emit)
        except BaseException as exc:
            restore_failure = type(exc).__name__ + ': ' + str(exc)
            emit('restoration_failed', error=restore_failure,
                 recovery_snapshot=str(directory / 'original.snapshot.json'))
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
    # Artifact handling is AFTER restoration and cannot bypass it.
    secrets = secret_values(original['environment'], candidate['environment'])
    log = directory / 'candidate.log'
    if log.exists():
        info = log.stat()
        require(info.st_size <= MAX_LOG, 'Viewer log exceeds download bound; full private board log retained')
        sanitized = redact(log.read_text(errors='replace'), secrets)
        with open(directory / 'candidate.redacted.log', 'x', encoding='utf-8') as stream:
            os.chmod(directory / 'candidate.redacted.log', 0o600)
            stream.write(sanitized)
    artifacts = []
    for name in ('candidate.redacted.log', 'proc.jsonl', 'trace.txt', 'trace.meta.json'):
        path = directory / name
        if path.exists():
            artifacts.append(dict(name=name, path=str(path), bytes=path.stat().st_size, sha256=sha(path)))
    emit('artifacts', files=artifacts)
    emit('finished', trial_error=failure, restore_error=restore_failure, restored=restore_failure is None)
    require(failure is None and restore_failure is None, 'Trial failed; inspect receipt and restoration outcome')

def action(request, emit):
    if request['action'] == 'diagnostic':
        return run_trial(request, emit)
    require(request['action'] == 'download', 'Unknown host stall action')
    artifact = request['artifact']
    require(re.fullmatch('/userdata/linaro/100h_performance/host_stall_[0-9a-f]{32}/'
                         '(candidate.redacted.log|proc.jsonl|trace.txt|trace.meta.json)', artifact['path']),
            'Invalid diagnostic artifact path')
    fd = os.open(artifact['path'], os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and stat.S_IMODE(info.st_mode) == 0o600,
                'Artifact is not a root-owned private file')
        require(info.st_size == artifact['bytes'] and info.st_size <= MAX_LOG, 'Artifact byte bound/size mismatch')
        require(sha('/proc/self/fd/' + str(stream.fileno())) == artifact['sha256'], 'Artifact hash changed')
        for block in iter(lambda: stream.read(65536), b''):
            emit('artifact_chunk', base64=base64.b64encode(block).decode('ascii'))
    emit('downloaded', name=artifact['name'], sha256=artifact['sha256'])
'''

REMOTE_MAIN = r'''
if __name__ == '__main__':
    def emit(state, **details):
        value = dict(state=state, **details)
        try:
            print(json.dumps(value), flush=True)
        except (BrokenPipeError, OSError):
            pass  # A disconnected parent must not cancel restoration.
    def expired(signum, frame):
        raise TimeoutError('Diagnostic supervisor deadline/interruption')
    try:
        request = json.loads(sys.stdin.read().splitlines()[-1])
        for number in (signal.SIGALRM, signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            signal.signal(number, expired)
        signal.setitimer(signal.ITIMER_REAL, request['timeout'] - 110 if request['action'] == 'diagnostic' else request['timeout'])
        action(request, emit)
    except BaseException as exc:
        emit('failed', error=type(exc).__name__ + ': ' + str(exc))
        sys.exit(1)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
'''


def remote_source(motion):
    return motion.REMOTE_SOURCE.split("if __name__ == '__main__':", 1)[0] + REMOTE_AGENT + REMOTE_MAIN


def measurement_from_receipt(receipt):
    starts = [e for e in receipt.get('events', []) if e.get('state') == 'measurement_started']
    endpoints = [e for e in receipt.get('events', []) if e.get('state') == 'measurement_endpoint']
    measured = [e for e in receipt.get('events', []) if e.get('state') == 'measured']
    if not starts or not (endpoints or measured):
        return None
    begin, end = starts[-1]['clocks'], (endpoints or measured)[-1]['clocks']
    identities = [e for e in receipt.get('events', []) if e.get('state') == 'candidate_identity']
    return dict(begin_clocks=begin, end_clocks=end, pid=identities[-1]['pid'] if identities else None,
                end_precedes_endpoint_verification=bool(endpoints),
                requested_seconds=receipt.get('seconds_limit'),
                observer_cpu_ns=end['sampler_cpu_ns'] - begin['sampler_cpu_ns'])


def analyze(log_text, samples, formats, trace_text='', measurement=None, trace_metadata=None, observer_cost=None):
    if trace_metadata and 'warnings' not in trace_metadata:
        # Older retained trace metadata has raw counters but no parsed warnings.
        trace_metadata = dict(trace_metadata, warnings=[])
        if trace_metadata.get('truncated'):
            trace_metadata['warnings'].append('Trace reached its byte ceiling; later events were not retained.')
        if any(int(value) > 0 for raw in trace_metadata.get('per_cpu_stats', {}).values()
               for value in re.findall(r'^(?:overrun|commit overrun|dropped events):\s*(\d+)\s*$', raw or '', re.M)):
            trace_metadata['warnings'].append('Trace per-CPU counters report lost/overwritten events.')
    allowed = {tag for values in formats.values() for value in values
               for tag in re.findall(r'\[([A-Za-z][A-Za-z0-9_.:-]*)\]', value)}
    rows = []
    for number, line in enumerate(log_text.splitlines(), 1):
        tags = re.findall(r'\[([A-Za-z][A-Za-z0-9_.:-]*)\]', line)
        if not any(tag in allowed for tag in tags):
            continue
        values = dict(re.findall(r'([A-Za-z_][A-Za-z0-9_.-]*)=([^\s,]+)', line))
        numeric = {}
        for key, value in values.items():
            try:
                candidate = int(value) if re.fullmatch(r'-?\d+', value) else float(value)
                if math.isfinite(candidate):
                    numeric[key] = candidate
            except ValueError:
                pass
        rows.append(dict(line_number=number, tags=tags, values=values, numeric=numeric, raw=line))
    stats = {}
    for tag in allowed:
        matching = [row for row in rows if tag in row['tags']]
        keys = {key for row in matching for key in row['numeric']}
        stats[tag] = dict(records=len(matching), numeric_fields={})
        for key in sorted(keys):
            values = sorted(row['numeric'][key] for row in matching if key in row['numeric'])
            stats[tag]['numeric_fields'][key] = dict(count=len(values), min=values[0], max=values[-1],
                                                    mean=sum(values) / len(values), p95=values[math.ceil(len(values) * .95) - 1])
    intervals = []
    for before, after in zip(samples, samples[1:]):
        old = {(t['tid'], t['starttime']): t for t in before['threads']}
        threads = []
        enabled = before.get('schedstats_enabled') == after.get('schedstats_enabled') == '1'
        for item in after['threads']:
            previous = old.get((item['tid'], item['starttime']))
            if previous is None:
                continue
            cpu_ms = (item['cpu_ticks'] - previous['cpu_ticks']) * 1000 / after['hz']
            a = (previous.get('schedstat') or '').split()
            b = (item.get('schedstat') or '').split()
            wait_ms = (int(b[1]) - int(a[1])) / 1e6 if enabled and len(a) == len(b) == 3 else None
            threads.append(dict(tid=item['tid'], starttime=item['starttime'], cpu_ms=cpu_ms,
                                sampled_state=item['state'], sampled_wchan=item.get('wchan'),
                                scheduler_wait_ms=wait_ms))
        gap = {key: (after['clocks'][key] - before['clocks'][key]) / 1e6
               for key in ('monotonic_ns', 'raw_ns', 'boottime_ns', 'realtime_ns')}
        intervals.append(dict(before_index=before['index'], after_index=after['index'],
                              clock_gaps_ms=gap, scheduler_wait_known=enabled, threads=threads,
                              observer_cpu_ms=(after['clocks']['sampler_cpu_ns'] - before['clocks']['sampler_cpu_ns']) / 1e6
                                              if 'sampler_cpu_ns' in before['clocks'] and 'sampler_cpu_ns' in after['clocks'] else None))
    signal_lines = [line for line in trace_text.splitlines() if 'signal_generate:' in line]
    decoded = decode_stall_windows(rows, samples)
    bounded = None
    if measurement:
        begin, end = measurement['begin_clocks']['monotonic_ns'], measurement['end_clocks']['monotonic_ns']
        contained, overlaps = [], []
        for row in rows:
            numeric = row['numeric']
            first, last = numeric.get('window_begin_ns'), numeric.get('window_end_ns')
            if first is None or last is None:
                prefix = 'syscall' if 'stall_ioctl' in row['tags'] else 'attempt'
                first, last = numeric.get(prefix + '_begin_ns'), numeric.get(prefix + '_end_ns')
            same_pid = measurement.get('pid') is None or numeric.get('pid') == measurement['pid']
            if first is None or last is None or last < first or not same_pid:
                continue
            if begin <= first <= last <= end:
                contained.append(row)
            elif first < end and last > begin:
                overlaps.append(row['line_number'])
        scoped = decode_stall_windows(contained, samples)
        scoped['metrics_scope'] = 'Complete logging windows/attempts wholly inside receipt measurement timestamps; boundary-crossing windows excluded, never prorated.'
        coverage = {}
        for row in scoped['camera']:
            key = str(row['camera'])
            coverage[key] = coverage.get(key, 0) + (row['seconds'] or 0)
        bounded = dict(**measurement, elapsed_seconds=(end - begin) / 1e9,
                       record_line_numbers=[row['line_number'] for row in contained],
                       boundary_crossing_line_numbers=overlaps, excluded_records=len(rows) - len(contained),
                       camera_coverage_seconds=coverage, stall_windows=scoped)
    known_cpu = [item for item in intervals if item['observer_cpu_ms'] is not None]
    max_cpu = max(known_cpu, key=lambda item: item['observer_cpu_ms']) if known_cpu else None
    return dict(schema=2, diagnostic_formats=formats, diagnostic_tags=sorted(allowed),
                 records=rows, field_summary=stats, proc_samples=len(samples), proc_intervals=intervals,
                 stall_windows=decoded, censored_tail=('[recover]' in log_text),
                 bounded_measurement=bounded, observer_cost=observer_cost,
                 observer_max_sample_interval=dict(cpu_ms=max_cpu['observer_cpu_ms'],
                                                  wall_ms=max_cpu['clock_gaps_ms']['monotonic_ns'],
                                                  before_index=max_cpu['before_index'], after_index=max_cpu['after_index']) if max_cpu else None,
                 trace_metadata=trace_metadata,
                 schedstats_enabled_values=sorted({str(s.get('schedstats_enabled')) for s in samples}),
                 signal_stop_continue_events=signal_lines,
                 limits=['Statistics use exactly the immutable header field names; units are not inferred.',
                         'Viewer records include startup and normal shutdown; proc intervals cover only bounded observation.',
                         'Bounded analysis includes only complete windows/attempts inside receipt timestamps; its camera coverage can be shorter than the measured duration.',
                         'Older receipts record their measured endpoint after final verification; that legacy endpoint cannot be separated retroactively.',
                        'Disabled schedstats means unknown scheduler wait. A sampled R state does not prove continuous runnable time.',
                        'Wall minus thread CPU alone does not separate blocking, descheduling and process group stop.',
                        'Trace is bounded and filters sampled TIDs; absence of an event is not proof of absence.',
                        'Five-second windows assign complete attempts at completion, including spans crossing the window.',
                        'All-completed windows count failures; slow lines are a thresholded subset. Immediate exit can lose deferred records.',
                        'Read/hold/ioctl/copy scopes are nested; their sums are not additive. Logger totals repeated across ioctl roles are not additive.'])


def decode_stall_windows(rows, samples):
    """Decode the inspected stall_timing.h schema; never mix units or outcomes."""
    camera = []
    ioctls = []
    stages = []
    slow = []
    anomalies = []
    stages_by_outcome = {}
    def number(row, key, default=None):
        return row['numeric'].get(key, default)
    def duration(row):
        first, last = number(row, 'window_begin_ns'), number(row, 'window_end_ns')
        return (last - first) / 1e9 if first is not None and last is not None and last > first else None
    def stats_for(row, prefix):
        total, invalid = number(row, prefix + '_n', 0), number(row, prefix + '_invalid', 0)
        valid = total - invalid
        wall, cpu = number(row, prefix + '_wall_sum_ns'), number(row, prefix + '_cpu_sum_ns')
        return dict(count=total, invalid=invalid, wall_sum_ns=wall, cpu_sum_ns=cpu,
                    wall_max_ns=number(row, prefix + '_wall_max_ns'), cpu_max_ns=number(row, prefix + '_cpu_max_ns'),
                    wall_mean_ms=wall / valid / 1e6 if valid > 0 and wall is not None else None,
                    cpu_mean_ms=cpu / valid / 1e6 if valid > 0 and cpu is not None else None,
                    non_thread_cpu_sum_ms=max(wall - cpu, 0) / 1e6 if wall is not None and cpu is not None else None)
    def identity(row):
        return dict(pid=number(row, 'pid'), tid=number(row, 'tid'), camera=number(row, 'camera'),
                    line_number=row['line_number'], window_begin_ns=number(row, 'window_begin_ns'),
                    window_end_ns=number(row, 'window_end_ns'))
    for row in rows:
        tags = row['tags']
        elapsed = duration(row)
        if 'stall_camera_window' in tags:
            counts = {key: number(row, key, 0) for key in ('success', 'error', 'no_new', 'unstable')}
            attempts = number(row, 'attempts', 0)
            if sum(counts.values()) != attempts:
                anomalies.append(dict(line_number=row['line_number'], reason='Camera outcome counts do not sum to attempts'))
            camera.append(dict(identity(row), seconds=elapsed, attempts=attempts, outcomes=counts,
                               completed_attempts_per_second=attempts / elapsed if elapsed else None,
                               delivered_per_second=counts['success'] / elapsed if elapsed else None,
                               logger_previous=stats_for(row, 'logger_previous'),
                               tag_advance_sum=number(row, 'tag_advance_sum'),
                               tag_comparisons=number(row, 'tag_comparisons'), tag_regressions=number(row, 'tag_regressions')))
        elif 'stall_ioctl_window' in tags:
            attempts, success, failure = (number(row, key, 0) for key in ('attempts', 'success', 'failure'))
            if success + failure != attempts:
                anomalies.append(dict(line_number=row['line_number'], reason='Ioctl outcome counts do not sum to attempts'))
            ioctls.append(dict(identity(row), role=row['values'].get('role'), seconds=elapsed, attempts=attempts,
                               success=success, failure=failure, rc_failure=number(row, 'rc_failure'),
                               alarm_failure=number(row, 'alarm_failure'), spans_window=number(row, 'spans_window'),
                               slow_overflow=number(row, 'slow_overflow'),
                               success_ioctl=stats_for(row, 'success_ioctl'), failure_ioctl=stats_for(row, 'failure_ioctl'),
                               legacy_log=stats_for(row, 'legacy_log'), logger_previous=stats_for(row, 'logger_previous')))
        elif 'stall_camera_stages' in tags:
            names = sorted(key[:-2] for key in row['numeric'] if key.endswith('_n'))
            outcome = row['values'].get('outcome')
            measured = {name: stats_for(row, name) for name in names}
            stages.append(dict(identity(row), outcome=outcome, seconds=elapsed,
                               attempts=number(row, 'attempts'), spans_window=number(row, 'spans_window'), stages=measured))
            # Per-outcome aggregation counts only disjoint completion windows.
            aggregate = stages_by_outcome.setdefault(str(outcome), {})
            for name, value in measured.items():
                total = aggregate.setdefault(name, dict(count=0, invalid=0, wall_sum_ns=0, cpu_sum_ns=0,
                                                        wall_max_ns=0, cpu_max_ns=0))
                for key in ('count', 'invalid', 'wall_sum_ns', 'cpu_sum_ns'):
                    total[key] += value[key] or 0
                for key in ('wall_max_ns', 'cpu_max_ns'):
                    total[key] = max(total[key], value[key] or 0)
        elif 'stall_ioctl' in tags or 'stall_camera' in tags:
            prefix = 'syscall' if 'stall_ioctl' in tags else 'attempt'
            begin, end = number(row, prefix + '_begin_ns'), number(row, prefix + '_end_ns')
            wall, cpu = number(row, prefix + '_wall_ns'), number(row, prefix + '_cpu_ns')
            nearby = [s['index'] for s in samples if begin is not None and end is not None and
                      begin - 1500000000 <= s['clocks']['monotonic_ns'] <= end + 1500000000]
            slow.append(dict(identity(row), record_kind=prefix, begin_ns=begin, end_ns=end,
                             wall_ms=wall / 1e6 if wall is not None else None,
                             cpu_ms=cpu / 1e6 if cpu is not None else None,
                             non_thread_cpu_ms=max(wall - cpu, 0) / 1e6 if wall is not None and cpu is not None else None,
                             low_thread_cpu=number(row, 'low_thread_cpu'), clock_valid=number(row, 'clock_valid'),
                             outcome=row['values'].get('outcome'), application_rc=number(row, 'application_rc'),
                             rc=number(row, 'rc'), errno=number(row, 'errno'), errno_valid=number(row, 'errno_valid'),
                             alarm=number(row, 'alarm'), nearby_proc_indices=nearby,
                             stages={key[:-2]: stats_for(row, key[:-2]) for key in row['numeric'] if key.endswith('_n')}))
    for outcome in stages_by_outcome.values():
        for value in outcome.values():
            valid = value['count'] - value['invalid']
            value['wall_mean_ms'] = value['wall_sum_ns'] / valid / 1e6 if valid > 0 else None
            value['cpu_mean_ms'] = value['cpu_sum_ns'] / valid / 1e6 if valid > 0 else None
    return dict(camera=camera, ioctl=ioctls, stages=stages, phase_totals_by_outcome=stages_by_outcome,
                slow=slow, accounting_anomalies=anomalies,
                metrics_scope='Whole candidate log; startup and graceful completion can contain shorter windows.')


def analysis_text(summary, receipt):
    decoded = summary['stall_windows']
    camera = decoded['camera']
    ioctl = decoded['ioctl']
    slow = decoded['slow']
    low = sum(row['low_thread_cpu'] == 1 for row in slow)
    body = [f"Diagnostic receipt status: {receipt['status']}.",
            f"HDMI restoration verified: {receipt.get('restoration_verified', False)}.",
             f"Retained {len(summary['records'])} diagnostic lines, {len(camera)} camera windows, "
            f"{len(ioctl)} ioctl windows and {summary['proc_samples']} proc samples.",
             f"Whole-log completed ioctl counts: {sum(w['attempts'] for w in ioctl)} attempts; "
            f"{sum(w['failure'] for w in ioctl)} application failures. These are completion-assigned counters.",
             f"Whole-log slow records: {len(slow)}; {low} have low thread CPU. This alone cannot identify the cause of the missing CPU time."]
    bounded = summary.get('bounded_measurement')
    if bounded:
        windows = bounded['stall_windows']
        body.append(f"Receipt measurement: {bounded['elapsed_seconds']:.6f} seconds; "
                    f"observer thread CPU {bounded['observer_cpu_ns'] / 1e9:.6f} seconds. "
                    f"Endpoint precedes final verification: {bounded['end_precedes_endpoint_verification']}.")
        body.append(f"Within measurement timestamps: {len(windows['camera'])} complete camera windows, "
                    f"{len(windows['ioctl'])} complete ioctl windows; "
                    f"{sum(w['attempts'] for w in windows['ioctl'])} ioctl attempts, "
                    f"{sum(w['failure'] for w in windows['ioctl'])} application failures. "
                    f"Excluded {bounded['excluded_records']} records, including "
                    f"{len(bounded['boundary_crossing_line_numbers'])} boundary-crossing records.")
        for camera_id in sorted({w['camera'] for w in windows['camera']}):
            selected = [w for w in windows['camera'] if w['camera'] == camera_id]
            seconds = sum(w['seconds'] or 0 for w in selected)
            counts = {key: sum(w['outcomes'][key] for w in selected)
                      for key in ('success', 'error', 'no_new', 'unstable')}
            body.append(f"Measured camera {camera_id}: {len(selected)} complete windows, {seconds:.6f} covered seconds; "
                        f"{counts['success']} delivered, {counts['error']} error, {counts['no_new']} no_new, "
                        f"{counts['unstable']} unstable; "
                        f"{counts['success'] / seconds:.3f} delivered/s over covered windows." if seconds else
                        f"Measured camera {camera_id}: no positive-duration window coverage.")
    observer = summary.get('observer_cost')
    if observer:
        body.append(f"Total observer cost: {observer['total']['cpu_ns'] / 1e9:.6f} CPU seconds, "
                    f"{observer['total']['wall_ns'] / 1e9:.6f} wall seconds. Scope: {observer['scope']}.")
        body.append(f"Maximum observer iteration CPU: {observer['max_iteration_cpu_ns'] / 1e6:.3f} ms; "
                    f"maximum paired interval CPU: {observer['max_cpu_interval_ns'] / 1e6:.3f} ms over "
                    f"{observer['max_cpu_interval_wall_ns'] / 1e6:.3f} wall ms. "
                    f"Global guards: {observer['global_guards']}; maximum start-to-start gap "
                    f"{observer['max_global_guard_gap_ns'] / 1e9:.6f} seconds.")
    interval = summary.get('observer_max_sample_interval')
    if interval:
        body.append(f"Maximum CPU interval between proc sample clocks: {interval['cpu_ms']:.3f} CPU ms "
                    f"paired with {interval['wall_ms']:.3f} wall ms.")
    trace = summary.get('trace_metadata') or {}
    body.extend(trace.get('warnings', []))
    phase_totals = (bounded['stall_windows'] if bounded else decoded)['phase_totals_by_outcome']
    body.append('Phase totals below use complete measurement windows.' if bounded else 'Phase totals below use the whole candidate log.')
    for outcome, phases in phase_totals.items():
        for phase, values in phases.items():
            if values['count'] and values['wall_mean_ms'] is not None:
                body.append(f"Outcome {outcome}, phase {phase}: {values['count']} scopes, "
                            f"mean wall {values['wall_mean_ms']:.3f} ms, mean CPU {values['cpu_mean_ms']:.3f} ms, "
                            f"maximum wall {values['wall_max_ns'] / 1e6:.3f} ms.")
    body += summary['limits']
    if summary['censored_tail'] or any(e.get('state') == 'trial_failed' for e in receipt['events']):
        body.append('Trial failure/recovery output indicates a potentially censored tail; do not interpret missing records as zero failures.')
    if decoded['accounting_anomalies']:
        body.append('Window accounting anomalies were found; inspect analysis.json before using counts.')
    return '\n\n'.join(body) + '\n'


def run(args, motion):
    build, formats, tests = validate_build(args.build_receipt, motion)
    cal = calibration_request(args.calibration_receipt, motion)
    proof = read_json(args.selftest_receipt) if args.selftest_receipt else build.get('selftest_proof')
    # Local --check can prepare an immutable build before the parent runs tests.
    if not args.check or proof:
        validate_proof(proof, build, tests, motion)
    if args.check:
        print(json.dumps(dict(valid=True, ssh=False, binary=build['binary'], test_options=tests,
                              restore_always=True, logging_formats=formats,
                              standalone_timing_proof_required=len(tests) == 2), indent=2))
        return 0
    from board_host import board_host, ssh_connect
    if cal['host'] != board_host():
        raise ValueError('Calibration receipt board host mismatch')
    token = uuid.uuid4().hex
    directory = HERE / 'runs' / ('diagnostic_' + token)
    directory.mkdir(parents=True)
    receipt_path = directory / 'receipt.json'
    receipt = dict(schema=1, operation=token, host=board_host(), status='running', restore_always=True,
                   seconds_limit=args.seconds, build_receipt=str(args.build_receipt.resolve()),
                   build_receipt_sha256=sha_file(args.build_receipt), binary_sha256=build['binary_sha256'],
                   snapshot_sha256=build['snapshot_sha256'], calibration_receipt_sha256=sha_file(args.calibration_receipt),
                   events=[], artifacts=[], remote_directory='/userdata/linaro/100h_performance/host_stall_' + token)
    current = dict(HDMI)
    if args.current_receipt:
        prior = read_json(args.current_receipt)
        candidates = [event for event in prior.get('events', []) if event.get('state') in ('restored', 'viewer_preserved')]
        if prior.get('status') != 'success' or not candidates:
            raise ValueError('Successful receipt with a verified current viewer is required')
        target = candidates[-1]
        if (type(target.get('pid')) is not int or target['pid'] <= 0 or
                not str(target.get('starttime', '')).isdigit() or
                target.get('exe_sha256', HDMI['exe_sha256']) != HDMI['exe_sha256']):
            raise ValueError('Receipt current viewer identity mismatch')
        current.update(pid=target['pid'], starttime=target['starttime'])
        receipt['current_receipt_sha256'] = sha_file(args.current_receipt)
    request = dict(action='diagnostic', operation=token, timeout=args.seconds + 400,
                   directory=receipt['remote_directory'], build=build, calibration=cal,
                    current=current, original_binary=ORIGINAL_BINARY, seconds=args.seconds,
                   tracefs=args.tracefs, test_options=tests, selftest_proof=proof)
    lock = LOG / 'board_session.lock'
    held = False
    request_sent = False
    client = None
    remote_error = None
    def event(value):
        receipt['events'].append(dict(value, local_received_monotonic_ns=time.monotonic_ns(),
                                      local_received_realtime_ns=time.time_ns()))
        if value['state'] == 'observer_finished':
            receipt['observer_cost'] = value['observer_cost']
            receipt['observation_policy'] = value['observation_policy']
        motion.viewer.atomic_json(receipt_path, receipt)
        if value['state'] != 'artifact_chunk':
            print('Diagnostic: ' + value['state'], flush=True)
        if value['state'] == 'measurement_started':
            policy = value['observation_policy']
            print('Observation cadence: sample %.1fs; global owner/interference guard %.1fs (subject to observer delays).' %
                  (policy['sample_period_seconds'], policy['global_guard_period_seconds']), flush=True)
            for limit in policy['limits']:
                print('Observation limit: ' + limit, flush=True)
        if value['state'] == 'trace_finished':
            for warning in value['metadata'].get('warnings', []):
                print('Trace warning: ' + warning, flush=True)
        if value['state'] == 'observer_finished':
            cost = value['observer_cost']
            print('Observer: %.6f CPU seconds total; %.3f ms maximum CPU interval paired with %.3f wall ms.' %
                  (cost['total']['cpu_ns'] / 1e9, cost['max_cpu_interval_ns'] / 1e6,
                   cost['max_cpu_interval_wall_ns'] / 1e6), flush=True)
    try:
        with lock.open('x', encoding='utf-8') as stream:
            json.dump(dict(operation=token, pid=os.getpid(), action='host_stall_diagnostic'), stream)
        held = True
        motion.viewer.atomic_json(receipt_path, receipt)
        motion.REMOTE_SOURCE = remote_source(motion)
        client = ssh_connect(timeout=8)
        try:
            request_sent = True
            motion.remote_run(client, request, event)
        except BaseException as exc:
            remote_error = type(exc).__name__ + ': ' + str(exc)
            receipt['remote_error'] = remote_error
        # Even a failed/crashed trial can have successfully restored and useful data.
        bundles = [e for e in receipt['events'] if e.get('state') == 'artifacts']
        for artifact in bundles[-1]['files'] if bundles else []:
            target = directory / artifact['name']
            with target.open('xb') as stream:
                def downloaded(value):
                    if value['state'] == 'artifact_chunk':
                        stream.write(base64.b64decode(value['base64'], validate=True))
                    elif value['state'] == 'downloaded':
                        receipt['artifacts'].append(dict(artifact, local_path=str(target)))
                    else:
                        event(value)
                motion.remote_run(client, dict(action='download', artifact=artifact, timeout=90), downloaded)
            if sha_file(target) != artifact['sha256'] or target.stat().st_size != artifact['bytes']:
                raise RuntimeError('Downloaded artifact size/hash mismatch')
        raw = directory / 'proc.jsonl'
        samples = [json.loads(line) for line in raw.read_text().splitlines()] if raw.exists() else []
        log = directory / 'candidate.redacted.log'
        trace = directory / 'trace.txt'
        trace_meta = directory / 'trace.meta.json'
        summary = analyze(log.read_text(encoding='utf-8') if log.exists() else '', samples, formats,
                          trace.read_text(encoding='utf-8') if trace.exists() else '',
                          measurement=measurement_from_receipt(receipt),
                          trace_metadata=read_json(trace_meta) if trace_meta.exists() else None,
                          observer_cost=receipt.get('observer_cost'))
        motion.viewer.atomic_json(directory / 'analysis.json', summary)
        receipt['analysis_sha256'] = sha_file(directory / 'analysis.json')
        restored = [e for e in receipt['events'] if e.get('state') == 'restored']
        measured = any(e.get('state') == 'measured' for e in receipt['events'])
        receipt['restoration_verified'] = bool(restored)
        receipt['restored_identity'] = restored[-1] if restored else None
        receipt['status'] = 'success' if remote_error is None and measured and restored and summary['records'] else 'failed'
        if not summary['records']:
            receipt['analysis_error'] = 'No immutable-header diagnostic records found; cannot claim diagnostic success'
        (directory / 'analysis.md').write_text(analysis_text(summary, receipt), encoding='utf-8')
        receipt['analysis_text_sha256'] = sha_file(directory / 'analysis.md')
        return 0 if receipt['status'] == 'success' else 1
    except BaseException as exc:
        receipt.update(status='failed', error=type(exc).__name__ + ': ' + str(exc))
        return 1
    finally:
        restored = any(e.get('state') == 'restored' for e in receipt['events'])
        receipt['restoration_verified'] = restored
        failed_before_snapshot = (bool(receipt['events']) and receipt['events'][-1].get('state') == 'failed' and
                                  not any(e.get('state') == 'snapshot_saved' for e in receipt['events']))
        release = not request_sent or restored or failed_before_snapshot
        receipt['board_lock_retained'] = held and not release
        motion.viewer.atomic_json(receipt_path, receipt)
        print('Receipt: ' + str(receipt_path), flush=True)
        if client:
            client.close()
        if held and release and read_json(lock).get('operation') == token:
            lock.unlink()


def self_test(motion):
    """Exercise failure recovery and identity refusal with no SSH or board writes."""
    from contextlib import contextmanager
    from tempfile import TemporaryDirectory
    import unittest
    from unittest.mock import Mock, patch
    namespace = {'__name__': 'local_diagnostic_test'}
    exec(compile(remote_source(motion), '<diagnostic supervisor>', 'exec'), namespace)

    @contextmanager
    def proc_fixture():
        # Real files and hard-linked live/disk executable inodes. Only proc path
        # routing/readlink are mocked so these tests also run on Windows.
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            proc = directory / 'proc'
            root = proc / '731'
            root.mkdir(parents=True)
            executable = directory / 'viewer'
            executable.write_bytes(b'actual executable fixture\n')
            os.link(executable, root / 'exe')
            cwd = directory / 'cwd'
            cwd.mkdir()
            boot_id = proc / 'sys/kernel/random/boot_id'
            boot_id.parent.mkdir(parents=True)
            boot_id.write_text('fixture-boot\n')
            config = dict(exe=str(executable.resolve()), cwd=str(cwd.resolve()),
                          argv=[str(executable.resolve()), '--model', 'fixture'],
                          env={'DISPLAY': ':0', 'PATH': '/usr/bin', 'UNCHANGED': '1'})
            baseline = dict(uid=0, gid=0, groups=[7, 9], boot_id='fixture-boot',
                            exe_sha256=sha_file(executable), files={str(executable): sha_file(executable)})
            target = dict(pid=731, starttime='777')
            common = dict(config=config, baseline=baseline, target=target)
            def write_stat(state='R', starttime='777'):
                fields = ['0'] * 50
                fields[0], fields[19] = state, starttime
                (root / 'stat').write_text('731 (fixture (name)) ' + ' '.join(fields) + '\n')
            def write_status(uid='0 0 0 0', gid='0 0 0 0', groups='7 9'):
                (root / 'status').write_text('Uid:\t' + uid + '\nGid:\t' + gid + '\nGroups:\t' + groups + '\n')
            write_stat()
            write_status()
            (root / 'cmdline').write_bytes(b'\0'.join(os.fsencode(v) for v in config['argv']) + b'\0')
            (root / 'environ').write_bytes(b'\0'.join(os.fsencode(k + '=' + v) for k, v in config['env'].items()) + b'\0')
            (root / 'fd').mkdir()
            (root / 'maps').write_text('')
            task = root / 'task/731'
            task.mkdir(parents=True)
            for name in ('stat', 'status'):
                (task / name).write_bytes((root / name).read_bytes())
            (task / 'schedstat').write_text('0 0 0\n')
            (task / 'wchan').write_text('fixture_wait\n')
            links = {root / 'exe': config['exe'], root / 'cwd': config['cwd']}
            native_readlink = os.readlink
            def readlink(path, *args, **kwargs):
                if Path(path) in links:
                    return links[Path(path)]
                return native_readlink(path, *args, **kwargs)
            def mapped_path(*args, **kwargs):
                if args and (str(args[0]) == '/proc' or str(args[0]).startswith('/proc/')):
                    return proc.joinpath(str(args[0])[len('/proc'):].lstrip('/'), *args[1:])
                return Path(*args, **kwargs)
            with patch.dict(namespace, PROC_ROOT=proc, Path=mapped_path), patch.object(os, 'readlink', readlink):
                yield dict(directory=directory, proc=proc, root=root, executable=executable, common=common,
                           links=links, write_stat=write_stat, write_status=write_status)

    class Tests(unittest.TestCase):
        def test_sample_identity_pins_live_sha_without_rehashing_each_sample(self):
            with proc_fixture() as fixture:
                hashed = Mock(wraps=namespace['sha'])
                with patch.dict(namespace, sha=hashed):
                    pinned = namespace['pin_sample_identity'](fixture['common'])
                    self.assertEqual(hashed.call_count, 1)
                    self.assertEqual(Path(hashed.call_args.args[0]), fixture['root'] / 'exe')
                    for _ in range(3):
                        self.assertEqual(namespace['sample_identity'](fixture['common'], pinned), pinned)
                    self.assertEqual(hashed.call_count, 1)

        def test_sample_identity_refuses_pid_reuse_and_zombie(self):
            for change in (dict(starttime='778'), dict(state='Z')):
                with self.subTest(change=change), proc_fixture() as fixture:
                    pinned = namespace['pin_sample_identity'](fixture['common'])
                    fixture['write_stat'](**change)
                    with self.assertRaisesRegex(RuntimeError, 'PID exited/reused'):
                        namespace['sample_identity'](fixture['common'], pinned)

        def test_sample_identity_refuses_same_content_disk_inode_replacement(self):
            with proc_fixture() as fixture:
                pinned = namespace['pin_sample_identity'](fixture['common'])
                replacement = fixture['directory'] / 'replacement'
                replacement.write_bytes(fixture['executable'].read_bytes())
                self.assertEqual(sha_file(replacement), fixture['common']['baseline']['exe_sha256'])
                os.replace(replacement, fixture['executable'])
                self.assertNotEqual(os.stat(fixture['root'] / 'exe').st_ino, os.stat(fixture['executable']).st_ino)
                with self.assertRaisesRegex(RuntimeError, 'live/disk executable metadata differ'):
                    namespace['sample_identity'](fixture['common'], pinned)

        def test_sample_identity_refuses_live_and_disk_metadata_change(self):
            with proc_fixture() as fixture:
                pinned = namespace['pin_sample_identity'](fixture['common'])
                fixture['executable'].write_bytes(b'changed executable contents with different size\n')
                with self.assertRaisesRegex(RuntimeError, 'identity metadata changed'):
                    namespace['sample_identity'](fixture['common'], pinned)

        def test_sample_identity_refuses_timestamp_change_without_size_or_inode_change(self):
            with proc_fixture() as fixture:
                pinned = namespace['pin_sample_identity'](fixture['common'])
                before = os.stat(fixture['executable'])
                os.utime(fixture['executable'], ns=(before.st_atime_ns, before.st_mtime_ns + 2000000000))
                after = os.stat(fixture['executable'])
                self.assertEqual((before.st_ino, before.st_size), (after.st_ino, after.st_size))
                self.assertNotEqual(before.st_mtime_ns, after.st_mtime_ns)
                with self.assertRaisesRegex(RuntimeError, 'identity metadata changed'):
                    namespace['sample_identity'](fixture['common'], pinned)

        def test_sample_identity_refuses_full_environment_argv_cwd_and_credentials(self):
            changes = ['env-value', 'env-extra', 'argv', 'cwd', 'exe-path', 'uid', 'effective-uid', 'gid', 'groups', 'boot']
            for change in changes:
                with self.subTest(change=change), proc_fixture() as fixture:
                    pinned = namespace['pin_sample_identity'](fixture['common'])
                    root = fixture['root']
                    if change == 'env-value':
                        (root / 'environ').write_bytes((root / 'environ').read_bytes().replace(b'UNCHANGED=1', b'UNCHANGED=2'))
                    elif change == 'env-extra':
                        with (root / 'environ').open('ab') as stream:
                            stream.write(b'EXTRA=unexpected\0')
                    elif change == 'argv':
                        (root / 'cmdline').write_bytes((root / 'cmdline').read_bytes().replace(b'fixture\0', b'other\0'))
                    elif change == 'cwd':
                        fixture['links'][root / 'cwd'] = str(fixture['directory'])
                    elif change == 'exe-path':
                        fixture['links'][root / 'exe'] += ' (deleted)'
                    elif change == 'uid':
                        fixture['write_status'](uid='1 1 1 1')
                    elif change == 'effective-uid':
                        fixture['write_status'](uid='0 1 0 0')
                    elif change == 'gid':
                        fixture['write_status'](gid='1 1 1 1')
                    elif change == 'groups':
                        fixture['write_status'](groups='7 10')
                    elif change == 'boot':
                        (fixture['proc'] / 'sys/kernel/random/boot_id').write_text('different-boot\n')
                    with self.assertRaises(RuntimeError):
                        namespace['sample_identity'](fixture['common'], pinned)

        def test_sample_identity_refuses_live_sha_changed_before_binding(self):
            with proc_fixture() as fixture:
                fixture['executable'].write_bytes(b'changed before initial pin\n')
                with self.assertRaisesRegex(RuntimeError, 'exe_sha256'):
                    namespace['pin_sample_identity'](fixture['common'])

        def test_target_owner_checks_descriptor_or_mapping_and_permission_errors(self):
            from types import SimpleNamespace
            with proc_fixture() as fixture:
                root = fixture['root']
                device_path = fixture['directory'] / 'device'
                device = SimpleNamespace(st_mode=namespace['stat'].S_IFCHR, st_rdev=91,
                                         st_dev=42, st_ino=73)
                descriptor = root / 'fd/4'
                descriptor.write_text('descriptor fixture')
                native_stat = os.stat
                def device_stat(path, *args, **kwargs):
                    if Path(path) in (device_path, descriptor):
                        return device
                    return native_stat(path, *args, **kwargs)
                # Only character-device stat fields need a Windows platform shim;
                # directory iteration and descriptor/map selection are real reads.
                with patch.dict(namespace, DEVICE=str(device_path)), patch.object(os, 'stat', device_stat):
                    self.assertTrue(namespace['target_owns_dma'](fixture['common']['target']))
                    descriptor.unlink()
                    major = os.major(device.st_dev) if hasattr(os, 'major') else 0
                    minor = os.minor(device.st_dev) if hasattr(os, 'minor') else device.st_dev
                    with patch.object(os, 'major', lambda value: major, create=True), \
                         patch.object(os, 'minor', lambda value: minor, create=True):
                        (root / 'maps').write_text('1000-2000 rw-s 00000000 %02x:%02x 73 /fixture/device\n' % (major, minor))
                        self.assertTrue(namespace['target_owns_dma'](fixture['common']['target']))
                        (root / 'maps').write_text('1000-2000 rw-s 00000000 %02x:%02x 74 /fixture/device\n' % (major, minor))
                        self.assertFalse(namespace['target_owns_dma'](fixture['common']['target']))
                native_iterdir = Path.iterdir
                def checked_iterdir(path):
                    if path == root / 'fd':
                        raise PermissionError('fixture inaccessible descriptors')
                    return native_iterdir(path)
                with patch.dict(namespace, DEVICE=str(device_path)), patch.object(os, 'stat', device_stat), \
                     patch.object(Path, 'iterdir', checked_iterdir):
                    with self.assertRaises(PermissionError):
                        namespace['target_owns_dma'](fixture['common']['target'])

        def test_trace_overrun_and_ceiling_warn_without_claiming_absence(self):
            stats = {'cpu0': 'overrun: 7\ncommit overrun: 2\ndropped events: 3\n'}
            decoded = namespace['trace_loss_summary'](stats, True)
            self.assertEqual(decoded['loss_counters'], dict(overrun=7, commit_overrun=2, dropped_events=3))
            self.assertTrue(decoded['loss_counters_complete'])
            self.assertEqual(len(decoded['warnings']), 2)
            self.assertIn('Unknown', decoded['scheduler_absence_interpretation'])
            self.assertFalse(namespace['trace_loss_summary']({'cpu0': None}, False)['loss_counters_complete'])
            legacy = analyze('', [], {}, trace_metadata=dict(truncated=True, per_cpu_stats=stats))
            self.assertEqual(len(legacy['trace_metadata']['warnings']), 2)

        def test_bounded_analysis_excludes_startup_shutdown_and_boundary_windows(self):
            formats = {'header': ['[stall_camera_window] pid=%d window_begin_ns=%lld window_end_ns=%lld']}
            lines = ['[stall_camera_window] pid=731 tid=731 camera=1 window_begin_ns=%d window_end_ns=%d attempts=1 success=1 error=0 no_new=0 unstable=0' % span
                     for span in [(0, 10), (5, 15), (10, 20), (15, 25), (20, 30)]]
            clocks = dict(monotonic_ns=10, sampler_cpu_ns=2)
            receipt = dict(seconds_limit=120, events=[dict(state='candidate_identity', pid=731),
                           dict(state='measurement_started', clocks=clocks),
                           dict(state='measurement_endpoint', clocks=dict(monotonic_ns=20, sampler_cpu_ns=5)),
                           dict(state='measured', clocks=dict(monotonic_ns=20, sampler_cpu_ns=5),
                                verification_end_clocks=dict(monotonic_ns=30, sampler_cpu_ns=8))])
            summary = analyze('\n'.join(lines), [], formats, measurement=measurement_from_receipt(receipt))
            self.assertEqual(len(summary['stall_windows']['camera']), 5)
            bounded = summary['bounded_measurement']
            self.assertEqual(bounded['record_line_numbers'], [3])
            self.assertEqual(bounded['boundary_crossing_line_numbers'], [2, 4])
            self.assertEqual(bounded['observer_cpu_ns'], 3)
            self.assertTrue(bounded['end_precedes_endpoint_verification'])
            self.assertEqual(bounded['camera_coverage_seconds'], {'1': 1e-8})
            receipt['events'] = [e for e in receipt['events'] if e['state'] != 'measurement_endpoint']
            self.assertFalse(measurement_from_receipt(receipt)['end_precedes_endpoint_verification'])

        def test_observation_guard_cadence_and_precise_endpoint_with_real_identity_reads(self):
            with proc_fixture() as fixture:
                now = dict(wall=0, cpu=0)
                def advance(wall_ns, cpu_ns):
                    now['wall'] += wall_ns
                    now['cpu'] += cpu_ns
                def clock():
                    return dict(monotonic_ns=now['wall'], raw_ns=now['wall'], boottime_ns=now['wall'],
                                realtime_ns=now['wall'], sampler_cpu_ns=now['cpu'])
                def sole_owner():
                    advance(100000000, 50000000)
                    return [731]
                def quiescent():
                    advance(100000000, 50000000)
                real_exact, real_verify = namespace['exact'], namespace['verify_files']
                def checked_exact(common):
                    result = real_exact(common)
                    advance(200000000, 100000000)
                    return result
                def checked_files(config, baseline):
                    real_verify(config, baseline)
                    advance(300000000, 150000000)
                directory = fixture['directory'] / 'observation'
                directory.mkdir()
                request = dict(directory=str(directory), seconds=21, operation='local', tracefs=False)
                saved = dict(candidate=fixture['common']['baseline'], candidate_config=fixture['common']['config'])
                events = []
                exact_spy, owner_spy = Mock(wraps=checked_exact), Mock(wraps=sole_owner)
                with patch.dict(namespace, clocks=clock, exact=exact_spy, verify_files=checked_files,
                                owners=owner_spy, measurement_quiescent=quiescent, target_owns_dma=lambda target: True,
                                private_write=lambda path, value: Path(path).write_text(json.dumps(value))), \
                     patch.object(namespace['time'], 'monotonic_ns', lambda: now['wall']), \
                     patch.object(namespace['time'], 'thread_time_ns', lambda: now['cpu']), \
                     patch.object(namespace['time'], 'sleep', lambda seconds: advance(round(seconds * 1e9), 0)), \
                     patch.object(namespace['os'], 'sysconf', lambda name: 100, create=True):
                    namespace['observe_trial'](request, saved, fixture['common']['target'],
                                               lambda state, **details: events.append(dict(state=state, **details)))
                self.assertEqual(exact_spy.call_count, 2)  # Full SHA only at observation boundaries.
                self.assertEqual(owner_spy.call_count, 4)  # Begin, 10s, 20s, end.
                measured = next(e for e in events if e['state'] == 'measured')
                self.assertEqual(measured['elapsed_seconds'], 21)
                self.assertEqual(measured['samples'], 21)
                self.assertEqual(measured['verification_end_clocks']['monotonic_ns'] - measured['clocks']['monotonic_ns'], 700000000)
                finished = next(e for e in events if e['state'] == 'observer_finished')['observer_cost']
                self.assertEqual(finished['measurement']['cpu_ns'], 200000000)
                self.assertEqual(finished['endpoint_verification']['cpu_ns'], 350000000)
                self.assertEqual(finished['max_cpu_interval_ns'], 100000000)
                samples = [json.loads(line) for line in (directory / 'proc.jsonl').read_text().splitlines()]
                self.assertEqual(len(samples), 21)
                self.assertNotIn('environment', samples[0]['observer']['identity'])
                self.assertNotIn('argv', samples[0]['observer']['identity'])
                self.assertTrue(samples[10]['observer']['global_guard'])
                self.assertEqual(samples[-1]['observer']['collection_end']['monotonic_ns'], measured['clocks']['monotonic_ns'] - 800000000)

        def test_observation_identity_failure_retains_cost_and_closes_artifacts(self):
            with proc_fixture() as fixture:
                directory = fixture['directory'] / 'failed-observation'
                directory.mkdir()
                events = []
                def clock():
                    wall = time.monotonic_ns()
                    return dict(monotonic_ns=wall, raw_ns=wall, boottime_ns=wall, realtime_ns=wall,
                                sampler_cpu_ns=time.thread_time_ns())
                def changed_owner_check(target):
                    with (fixture['root'] / 'environ').open('ab') as stream:
                        stream.write(b'EXTRA=changed-during-sample\0')
                    return True
                request = dict(directory=str(directory), seconds=1, operation='local', tracefs=False)
                saved = dict(candidate=fixture['common']['baseline'], candidate_config=fixture['common']['config'])
                with patch.dict(namespace, clocks=clock, owners=lambda: [731], measurement_quiescent=Mock(),
                                target_owns_dma=changed_owner_check,
                                private_write=lambda path, value: Path(path).write_text(json.dumps(value))), \
                     patch.object(namespace['time'], 'monotonic_ns', time.perf_counter_ns), \
                     patch.object(namespace['os'], 'sysconf', lambda name: 100, create=True):
                    with self.assertRaisesRegex(RuntimeError, 'full environment changed'):
                        namespace['observe_trial'](request, saved, fixture['common']['target'],
                                                   lambda state, **details: events.append(dict(state=state, **details)))
                states = [e['state'] for e in events]
                self.assertIn('measurement_aborted', states)
                self.assertIn('trace_finished', states)
                self.assertNotIn('measured', states)
                cost = next(e for e in events if e['state'] == 'observer_finished')['observer_cost']
                self.assertGreater(cost['total']['wall_ns'], 0)
                self.assertGreater(cost['measurement']['wall_ns'], 0)
                # Windows thread CPU ticks can remain zero for this short test.
                self.assertGreaterEqual(cost['total']['cpu_ns'], 0)
                self.assertGreaterEqual(cost['measurement']['cpu_ns'], 0)
                self.assertGreaterEqual(cost['max_cpu_interval_ns'], 0)
                self.assertEqual(cost['samples'], 0)
                for name in ('proc.jsonl', 'trace.txt'):
                    os.replace(directory / name, directory / (name + '.closed'))

        def test_disabled_schedstats_is_unknown(self):
            a = dict(index=0, hz=100, schedstats_enabled='0', clocks={k: 0 for k in
                     ('monotonic_ns', 'raw_ns', 'boottime_ns', 'realtime_ns')},
                     threads=[dict(tid=7, starttime='9', state='R', cpu_ticks=100, schedstat='0 0 0')])
            b = dict(a, index=1, clocks={k: 20000000000 for k in a['clocks']},
                     threads=[dict(tid=7, starttime='9', state='R', cpu_ticks=102, schedstat='0 0 0')])
            summary = analyze('', [a, b], {})
            self.assertIsNone(summary['proc_intervals'][0]['threads'][0]['scheduler_wait_ms'])
            self.assertEqual(summary['proc_intervals'][0]['threads'][0]['cpu_ms'], 20)

        def test_header_drives_parser_and_keeps_failures(self):
            formats = {'new.h': logging_formats('fprintf(f, "[attempt] rc=%d " "wall_ns=%lld cpu_ns=%lld\\n", x);')}
            summary = analyze('[attempt] rc=-1 wall_ns=9000 cpu_ns=2\n[old] wall_ns=1', [], formats)
            self.assertEqual(len(summary['records']), 1)
            self.assertEqual(summary['records'][0]['numeric']['rc'], -1)
            self.assertEqual(summary['field_summary']['attempt']['numeric_fields']['wall_ns']['max'], 9000)

        def test_real_header_synthetic_log_counts_all_outcomes(self):
            header = (HERE / 'diagnostic/stall_timing.h').read_text(encoding='utf-8')
            validation = read_json(HERE / 'diagnostic/validation/validation.json')
            outputs = [item['stderr'] for item in validation['commands']
                       if item.get('returncode') == 0 and '[stall_ioctl_window]' in item.get('stderr', '')]
            self.assertTrue(outputs)
            summary = analyze('\n'.join(outputs), [], {'stall_timing.h': logging_formats(header)})
            decoded = summary['stall_windows']
            self.assertTrue(decoded['camera'])
            self.assertTrue(decoded['ioctl'])
            self.assertFalse(decoded['accounting_anomalies'])
            outcomes = {row['outcome'] for row in decoded['stages']}
            self.assertEqual(outcomes, {'success', 'error', 'no_new', 'unstable'})
            self.assertGreater(sum(row['failure'] for row in decoded['ioctl']), 0)
            self.assertTrue(any(row['application_rc'] == -1 and row['rc'] == 0 and row['alarm'] == 1
                                for row in decoded['slow']))

        def test_standalone_timing_proof_must_pin_target_header(self):
            header_hash = sha_file(HERE / 'diagnostic/stall_timing.h')
            tests = ['--vision-selftest', '--camera-dma-selftest']
            build = dict(binary_sha256='a' * 64, source_sha256={'stall_timing.h': header_hash})
            proof = dict(binary_sha256='a' * 64,
                         tests=[dict(option=option, exit_code=0, output_sha256='b' * 64) for option in tests],
                         timing=dict(exit_code=0, machine='aarch64', binary_sha256='c' * 64,
                                     output_sha256='d' * 64, source_sha256={'stall_timing.h': header_hash,
                                         'stall_timing_selftest.cpp': sha_file(HERE / 'diagnostic/stall_timing_selftest.cpp')}))
            validate_proof(proof, build, tests, motion)
            proof['timing']['source_sha256']['stall_timing.h'] = 'e' * 64
            with self.assertRaises(ValueError):
                validate_proof(proof, build, tests, motion)

        def test_current_pid_reuse_never_closes(self):
            close = Mock()
            with patch.dict(namespace, owners=lambda: [109952], process=lambda pid: dict(HDMI, starttime='reused'),
                            close_window=close):
                with self.assertRaises(RuntimeError):
                    namespace['check_current'](HDMI, {})
            close.assert_not_called()

        def test_restore_refuses_other_dma_owner(self):
            close, launch = Mock(), Mock()
            saved = dict(original=dict(HDMI), original_config={}, candidate_config={'exe': '/candidate'}, candidate={})
            with patch.dict(namespace, verify_files=Mock(), process=lambda pid: None, owners=lambda: [999],
                            close_exact=close, original_action=launch):
                with self.assertRaises(RuntimeError):
                    namespace['restore_hdmi']({'directory': '/private'}, saved, None, Mock())
            close.assert_not_called()
            launch.assert_not_called()

        def test_secrets_redacted(self):
            env = {'PATH': '/usr/bin', 'ACCESS_TOKEN': 'secret123', 'PASSWORD': 'p'}
            self.assertEqual(namespace['redact']('secret123 p /usr/bin', namespace['secret_values'](env)),
                             '<redacted> <redacted> /usr/bin')

        def test_no_viewer_signals_or_global_trace_mutation(self):
            self.assertNotIn('os.kill', REMOTE_AGENT)
            self.assertNotIn('SIGSTOP', REMOTE_AGENT)
            self.assertNotIn('SIGCONT', REMOTE_AGENT)
            self.assertNotIn('rmmod', REMOTE_AGENT)
            self.assertNotIn('shutil.rmtree', REMOTE_AGENT)

        def test_recovery_after_startup_and_measurement_failure(self):
            from tempfile import TemporaryDirectory
            old = dict(pid=12, starttime='34', exe='/original', exe_sha256='a' * 64,
                       argv=['/original'], cwd='/cwd', environment={}, files={}, uid=0, gid=0, groups=[])
            build = dict(binary='/candidate', binary_sha256='b' * 64, source_sha256={}, remote_directory='/build')
            for where in ('tests', 'close', 'start', 'observe'):
                with TemporaryDirectory() as directory:
                    requested = str(Path(directory) / 'run')
                    request = dict(build=build, current={}, calibration={}, directory=requested,
                                   operation='test', test_options=[], tracefs=False, seconds=1)
                    restore = Mock()
                    def start(req, emit):
                        emit('candidate_identity', pid=14, starttime='56', exe_sha256='b' * 64)
                        if where == 'start':
                            raise RuntimeError('startup failed')
                    mocks = dict(check_build=Mock(), boot=lambda: 'boot', load_calibration=lambda req: dict(old),
                                 check_current=lambda expected, prior: dict(old), private_write=Mock(), sha=lambda path: 'c' * 64,
                                 process=lambda pid: dict(old, pid=14, starttime='56'), exact=Mock(), verify_files=Mock(),
                                 measurement_quiescent=Mock(), owners=lambda: [], restore_hdmi=restore, candidate_action=start,
                                 no_dma_tests=Mock(side_effect=RuntimeError('tests failed') if where == 'tests' else None),
                                 close_exact=Mock(side_effect=RuntimeError('close failed') if where == 'close' else None),
                                 observe_trial=Mock(side_effect=RuntimeError('observation failed') if where == 'observe' else None))
                    with patch.dict(namespace, mocks), \
                         patch.object(namespace['signal'], 'setitimer', Mock(), create=True), \
                         patch.object(namespace['signal'], 'ITIMER_REAL', 0, create=True), \
                         patch.object(namespace['os'], 'chmod', Mock()), \
                         patch.object(namespace['stat'], 'S_IMODE', lambda mode: 0o700):
                        # Windows is not uid-bearing; intercept only the directory ownership check.
                        native_stat = Path.stat
                        def checked_stat(path, **kwargs):
                            value = native_stat(path, **kwargs)
                            if str(path) == requested:
                                return type('PrivateInfo', (), {'st_uid': 0, 'st_mode': value.st_mode})()
                            return value
                        with patch.object(Path, 'stat', checked_stat):
                            with self.assertRaises(RuntimeError):
                                namespace['run_trial'](request, Mock())
                    restore.assert_called_once()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    return 0 if result.wasSuccessful() else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--build-receipt', type=Path)
    parser.add_argument('--calibration-receipt', type=Path, default=CAL_CAPTURE)
    parser.add_argument('--selftest-receipt', type=Path,
                        help='Passed viewer tests and, when separate, target timing proof; see module docstring')
    parser.add_argument('--current-receipt', type=Path,
                        help='Successful restoration receipt pinning the current HDMI PID/starttime')
    parser.add_argument('--seconds', type=int, default=120)
    parser.add_argument('--restore', action='store_true', default=True, help='Always enabled; no leave-running mode')
    parser.add_argument('--tracefs', action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument('--check', action='store_true', help='Validate local frozen inputs/receipts only; no SSH')
    parser.add_argument('--self-test', action='store_true', help='Run local mocked recovery/analysis tests only; no SSH')
    args = parser.parse_args()
    if not 1 <= args.seconds <= 120:
        parser.error('--seconds must be in [1, 120]')
    if not args.self_test and args.build_receipt is None:
        parser.error('--build-receipt is REQUIRED except for local --self-test')
    motion = load_helpers()
    if args.self_test:
        return self_test(motion)
    try:
        return run(args, motion)
    except (ValueError, OSError, KeyError, RuntimeError) as exc:
        print(type(exc).__name__ + ': ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
