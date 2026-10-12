"""Reviewable RGB888 trial orchestration. Default is a local plan, never SSH.

Execute only after the parent's original-display baseline capture has finished.
No signal is sent to a DMA owner. Failed/uncertain runs preserve the board for
explicit recovery. Results measure paired inference stages, not live viewer FPS.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import shlex
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
MODEL = '/root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v8_w25_nop2c2f-rk3568-raw-dfl6-int8.rknn'
MODEL_SHA = 'be7ee818eef1cb916c9706580a1b58426fc047c60df12b80d341646dfbbd2cf9'
BATCH_SHA = '81eb0c05b40eff2887f1b81770fece6beafedc25f77fd1bbfbebe487e9dbb192'
ORIGINAL_SHA = 'fcb2e44d5b97d9857e72610d543300e747dcc4a822e8797bbf5d5418ddd01122'
VIEWER_SHA = '73613d525541939ea493a9bb87eeeae10879c4a08eede36a7ee298777fb32100'
ACTIVE = '/userdata/detview-hdmifull/detview-hdmifull'
BACKUP = ACTIVE + '.before-latency-fix-20261008'
ABI = Path('D:/race/ov56401/project/fpga_v8_migration/cooperative_linux_transport/driver_abi.hpp')

# Uploaded only with --execute. Xlib uses native longs for 32-bit properties.
REMOTE_HELPER = r'''
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import sys

DEVICE = '/dev/pango_pci_driver'
def process(pid):
    base = Path('/proc') / str(pid)
    text = (base / 'stat').read_text().rsplit(')', 1)[1].split()
    exe = os.readlink(str(base / 'exe'))
    return {'pid': int(pid), 'state': text[0], 'starttime': text[19],
            'exe': exe, 'sha256': hashlib.sha256((base / 'exe').read_bytes()).hexdigest(),
            'cmdline': (base / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')}

def owners():
    result = []
    dev = Path(DEVICE)
    if not dev.exists():
        raise RuntimeError('Device node missing; ownership cannot be established')
    for base in Path('/proc').iterdir():
        if not base.name.isdigit():
            continue
        try:
            found = False
            for fd in (base / 'fd').iterdir():
                try:
                    target = os.readlink(str(fd))
                    if target == DEVICE or target.startswith(DEVICE + ' '):
                        found = True
                except FileNotFoundError:
                    pass
            if found:
                result.append(process(base.name))
        except FileNotFoundError:
            continue
        # Permission errors intentionally fail rather than implying no owner.
    return result

class Key(C.Structure):
    _fields_ = [('type', C.c_int), ('serial', C.c_ulong), ('send_event', C.c_int),
                ('display', C.c_void_p), ('window', C.c_ulong), ('root', C.c_ulong),
                ('subwindow', C.c_ulong), ('time', C.c_ulong), ('x', C.c_int),
                ('y', C.c_int), ('x_root', C.c_int), ('y_root', C.c_int),
                ('state', C.c_uint), ('keycode', C.c_uint), ('same_screen', C.c_int)]
class Event(C.Union):
    _fields_ = [('key', Key), ('pad', C.c_long * 24)]

def quit_ui(pid, start, sha, symbol):
    expected = process(pid)
    if (expected['starttime'] != start or expected['sha256'] != sha or
            expected['state'] in ('T', 't', 'Z', 'D') or
            [r['pid'] for r in owners()] != [pid]):
        raise RuntimeError('Viewer identity/state/sole ownership changed')
    x = C.CDLL('libX11.so.6')
    signatures = {
        'XOpenDisplay': ([C.c_char_p], C.c_void_p),
        'XDefaultRootWindow': ([C.c_void_p], C.c_ulong),
        'XInternAtom': ([C.c_void_p, C.c_char_p, C.c_int], C.c_ulong),
        'XQueryTree': ([C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong), C.POINTER(C.c_ulong),
                        C.POINTER(C.POINTER(C.c_ulong)), C.POINTER(C.c_uint)], C.c_int),
        'XGetWindowProperty': ([C.c_void_p, C.c_ulong, C.c_ulong, C.c_long, C.c_long,
            C.c_int, C.c_ulong, C.POINTER(C.c_ulong), C.POINTER(C.c_int),
            C.POINTER(C.c_ulong), C.POINTER(C.c_ulong), C.POINTER(C.c_void_p)], C.c_int),
        'XFree': ([C.c_void_p], C.c_int),
        'XStringToKeysym': ([C.c_char_p], C.c_ulong),
        'XKeysymToKeycode': ([C.c_void_p, C.c_ulong], C.c_uint),
        'XSendEvent': ([C.c_void_p, C.c_ulong, C.c_int, C.c_long, C.POINTER(Event)], C.c_int),
        'XSync': ([C.c_void_p, C.c_int], C.c_int),
        'XCloseDisplay': ([C.c_void_p], C.c_int)}
    for name, (inputs, output) in signatures.items():
        func = getattr(x, name)
        func.argtypes, func.restype = inputs, output
    display = x.XOpenDisplay(None)
    if not display:
        raise RuntimeError('Cannot open production X display')
    try:
        root = x.XDefaultRootWindow(display)
        atom = x.XInternAtom(display, b'_NET_WM_PID', 1)
        if not atom:
            raise RuntimeError('No _NET_WM_PID atom')
        windows, todo, seen = [], [root], set()
        while todo:
            window = todo.pop()
            if window in seen:
                continue
            seen.add(window)
            actual, count, remaining = C.c_ulong(), C.c_ulong(), C.c_ulong()
            fmt, data = C.c_int(), C.c_void_p()
            rc = x.XGetWindowProperty(display, window, atom, 0, 1, 0, 6,
                C.byref(actual), C.byref(fmt), C.byref(count), C.byref(remaining), C.byref(data))
            if rc == 0 and data.value:
                try:
                    if actual.value == 6 and fmt.value == 32 and count.value == 1:
                        if C.cast(data, C.POINTER(C.c_ulong))[0] == pid:
                            windows.append(window)
                finally:
                    x.XFree(data)
            tree_root, parent, children, n = C.c_ulong(), C.c_ulong(), C.POINTER(C.c_ulong)(), C.c_uint()
            if x.XQueryTree(display, window, C.byref(tree_root), C.byref(parent), C.byref(children), C.byref(n)):
                todo.extend(children[i] for i in range(n.value))
                if children:
                    x.XFree(C.cast(children, C.c_void_p))
        if len(windows) != 1:
            raise RuntimeError('Expected exactly one PID-matched Qt window: ' + repr(windows))
        current = process(pid)
        if current['starttime'] != start or current['sha256'] != sha:
            raise RuntimeError('PID reused before key dispatch')
        code = x.XKeysymToKeycode(display, x.XStringToKeysym(symbol.encode()))
        if not code:
            raise RuntimeError('Quit key has no keycode')
        for event_type, mask in ((2, 1), (3, 2)):
            event = Event()
            event.key.type, event.key.send_event = event_type, 1
            event.key.display, event.key.window, event.key.root = display, windows[0], root
            event.key.keycode, event.key.same_screen = code, 1
            if not x.XSendEvent(display, windows[0], 0, mask, C.byref(event)):
                raise RuntimeError('XSendEvent failed')
        x.XSync(display, 0)
        print(json.dumps({'pid': pid, 'window': windows[0], 'key': symbol, 'method': 'XSendEvent'}))
    finally:
        x.XCloseDisplay(display)

if sys.argv[1] == 'owners':
    print(json.dumps(owners()))
elif sys.argv[1] == 'process':
    print(json.dumps(process(int(sys.argv[2]))))
elif sys.argv[1] == 'retired':
    pid, start = int(sys.argv[2]), sys.argv[3]
    try:
        current = process(pid)
        retired = current['starttime'] != start or current['state'] == 'Z'
    except FileNotFoundError:
        retired = True
    print(json.dumps({'retired': retired, 'owners': owners()}))
elif sys.argv[1] == 'quit':
    quit_ui(int(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5])
else:
    raise RuntimeError('Unknown helper operation')
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize_pairs(text, pairs, shared):
    rows = [json.loads(line) for line in text.splitlines() if line.startswith('{')]
    identity = [row for row in rows if row.get('kind') == 'identity']
    measured = [row for row in rows if row.get('kind') == 'pair']
    if (len(identity) != 1 or not rows or rows[-1] != {'kind': 'pass', 'pairs': pairs}
            or len(measured) != pairs):
        raise RuntimeError('Missing exact identity/pair/completion receipts')
    if shared and (identity[0].get('baseline_init_flags') != 0 or identity[0].get('shared_init_flags') != 16384):
        raise RuntimeError('Shared flags differ from the existing harness')
    if not shared and identity[0].get('input_mode') != 'borrowed coherent RX pointer with inputs_set; not DMA-BUF zero-copy':
        raise RuntimeError('Conventional arm is not the existing inputs_set path')
    if identity[0].get('output_comparison') != 'native output byte parity':
        raise RuntimeError('Missing native output comparison identity')
    if any(row.get('input_parity') is not True or row.get('output_parity') is not True for row in measured):
        raise RuntimeError('Input/native output parity failed')
    keys = ('claim_ms', 'raw_dma_copy_ms', 'cpu_preprocess_ms', 'fpga_to_rx_slot_ms',
            'cpu_rknn_ms', 'fpga_rknn_ms', 'cpu_inputs_set_ms', 'fpga_submit_or_lease_ms',
            'release_ms', 'cpu_total_ms', 'fpga_total_ms',
            'cpu_path_process_cpu_ms', 'fpga_path_process_cpu_ms')
    summary = {'pairs': pairs, 'identity': identity[0], 'input_parity': True, 'output_parity': True,
               'scope': 'paired inference stage FPS; excludes viewer/rendering throughput',
               'arm': 'shared DMA-BUF' if shared else 'RGB conversion only; inputs_set on both paths'}
    for key in keys:
        values = [row[key] for row in measured]
        if any(not isinstance(v, (float, int)) or not math.isfinite(v) or v < 0 for v in values):
            raise RuntimeError('Invalid measured timing: ' + key)
        summary[key] = sum(values) / len(values)
    for side in ('cpu', 'fpga'):
        if summary[side + '_total_ms'] <= 0:
            raise RuntimeError('Nonpositive stage duration')
        summary[side + '_stage_fps'] = 1000 / summary[side + '_total_ms']
    summary['stage_fps_change_percent'] = (summary['fpga_stage_fps'] / summary['cpu_stage_fps'] - 1) * 100
    return summary


def viewer_metrics(text):
    displays = re.findall(r'\[display-perf\].*?seconds=([\d.]+).*?new_paint_fps=([\d.]+).*?swap_fps=([\d.]+)', text)
    captures = re.findall(r'\[capture\] camera=(\d+) delivered_fps=([\d.]+) tag_advance_rate=([\d.]+).*?unstable=(\d+)', text)
    stats = re.findall(r'\[stats\].*?npu_completed_fps=([\d.]+) npu_failed_fps=([\d.]+)', text)
    if not displays or not stats or {int(c[0]) for c in captures} != set(range(1, 7)):
        raise RuntimeError('Missing six-camera/display/inference health evidence')
    if any(int(c[3]) for c in captures) or any(float(s[1]) for s in stats):
        raise RuntimeError('Unstable capture or failed inference in viewer health log')
    if sum(float(d[0]) for d in displays) < 85:
        raise RuntimeError('Viewer health evidence covers less than 85 seconds')
    weight = sum(float(d[0]) for d in displays)
    result = {'new_paint_fps': sum(float(d[0]) * float(d[1]) for d in displays) / weight,
              'swap_fps': sum(float(d[0]) * float(d[2]) for d in displays) / weight,
              'npu_completed_fps': sum(float(s[0]) for s in stats) / len(stats),
              'cameras': {str(i): sum(float(c[1]) for c in captures if int(c[0]) == i) /
                          sum(int(c[0]) == i for c in captures) for i in range(1, 7)}}
    if any(v <= 0 for v in (result['new_paint_fps'], result['swap_fps'], result['npu_completed_fps'], *result['cameras'].values())):
        raise RuntimeError('Viewer has no measured progress')
    return result


def validate_local():
    for path, expected in ((ROOT / 'integrated_six_batch/project/generate_bitstream/top.sbit', BATCH_SHA),
                           (ROOT.parent / 'bitstream_cam5_fix_20261008/top.sbit', ORIGINAL_SHA)):
        if sha(path) != expected:
            raise RuntimeError('Pinned image identity mismatch: ' + str(path))
    generated = json.loads((ROOT / 'six_batch_bitstream_manifest.json').read_text())
    build = json.loads((ROOT / 'six_batch_pds_manifest.json').read_text())
    timing = ROOT / 'integrated_six_batch/project/place_route/top_timing_summary_after_hold_fix.txt'
    if (generated.get('status') != 'finished' or generated.get('return_code') != 0 or
            generated.get('sha256') != BATCH_SHA or generated.get('timing_sha256') != sha(timing) or
            'All Constraints Met' not in timing.read_text() or
            build.get('status') != 'finished' or build.get('return_code') != 0):
        raise RuntimeError('Batch timing/build receipt invalid')
    for relative, expected in build['inputs'].items():
        path = ROOT / relative
        if path.name != 'project.pds' and sha(path) != expected:
            raise RuntimeError('Batch source changed: ' + relative)
    sources = list((ROOT / 'host').glob('*.hpp')) + [ROOT / 'host/paired_pointer.cpp',
        ROOT.parent / 'display_latency_delivery/src/rknn_api.h', ROOT / 'driver/pango_zc_uapi.h', ABI]
    for source in sources:
        if not source.is_file():
            raise RuntimeError('Missing build source: ' + str(source))
    return build, sources


def stage_program(folder, build):
    """Use the existing programmer unchanged; isolate every fixed output path."""
    parent = folder / 'program_workspace'
    staged = parent / 'fpga_zero_copy_delivery'
    staged.mkdir(parents=True)
    files = {'program_fpga.py', 'six_batch_bitstream_manifest.json', 'six_batch_pds_manifest.json',
             'integrated_six_batch/project/generate_bitstream/top.sbit',
             'integrated_six_batch/project/place_route/top_timing_summary_after_hold_fix.txt'}
    files.update(build['inputs'])
    for relative in files:
        source = (ROOT / relative).resolve()
        source.relative_to(ROOT)  # Reject escaping paths before copying.
        dest = staged / source.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    for name in ('board_ssh.py', 'flash_repo_latest.py'):
        shutil.copy2(ROOT.parent / name, parent / name)
    dest = parent / 'bitstream_cam5_fix_20261008/top.sbit'
    dest.parent.mkdir()
    shutil.copy2(ROOT.parent / 'bitstream_cam5_fix_20261008/top.sbit', dest)
    return staged


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Enable SSH, SRAM programming and trials (default: local plan only)')
    parser.add_argument('--viewer-pid', type=int, help='Verified current production owner; required for execution')
    parser.add_argument('--baseline-log', type=Path, help='Completed parent 95-second original display health log')
    parser.add_argument('--min-fps-ratio', type=float, default=0.85, help='Minimum restored/baseline FPS for display, inference and each camera')
    parser.add_argument('--quit-key', choices=('q', 'Escape'), default='q')
    args = parser.parse_args()
    if not 0 < args.min_fps_ratio <= 1:
        parser.error('--min-fps-ratio must be in (0, 1]')
    if not args.execute:
        print('LOCAL PLAN ONLY: no board access or files written. Execution requires completed baseline and current owner PID.')
        print('Build isolated paired_pointer and paired_shared; graceful PID-verified X11 quit; require owner retirement;')
        print('program pinned batch SRAM once; run each harness with 10 warmups and 240 alternating pairs;')
        print('require exact RGB/native-output parity and retired owner after each; restore pinned original SRAM;')
        print('launch pinned original viewer; capture 95 seconds and compare original viewer FPS with baseline.')
        print('Any uncertain failure preserves board state; no SIGTERM/force-program fallback. This is not live RGB888 viewer integration.')
        return 0
    if not args.viewer_pid or args.viewer_pid <= 1 or not args.baseline_log:
        parser.error('--execute requires --viewer-pid and --baseline-log after parent baseline finishes')
    baseline = viewer_metrics(args.baseline_log.read_text(encoding='utf-8', errors='replace'))
    build, sources = validate_local()
    folder = ROOT / ('rgb888_trial_' + str(time.time_ns()))
    folder.mkdir()
    staged = stage_program(folder, build)
    remote = '/userdata/linaro/' + folder.name
    helper = folder / 'trial_helper.py'
    helper.write_text(REMOTE_HELPER, encoding='utf-8')
    compile(REMOTE_HELPER, str(helper), 'exec')
    shutil.copy2(args.baseline_log, folder / 'baseline_acceptance.log')
    manifest = {'status': 'preflight', 'remote': remote, 'baseline': baseline, 'warmup': 10, 'pairs': 240,
                'model_sha256': MODEL_SHA, 'batch_sha256': BATCH_SHA, 'original_sha256': ORIGINAL_SHA,
                'viewer_sha256': VIEWER_SHA, 'sources': {str(p): sha(p) for p in sources}}
    def save():
        (folder / 'trial.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    save()
    sys.path.insert(0, str(ROOT.parent))
    import board_ssh
    client = board_ssh.connect()
    counter = 0
    def run(command, label, timeout=30, sudo=True):
        nonlocal counter
        counter += 1
        rc, out, err = board_ssh.run(client, command, sudo=sudo, timeout=timeout)
        (folder / ('%03d_%s.log' % (counter, label))).write_text(out + err, encoding='utf-8')
        if rc:
            raise RuntimeError('%s failed (%s): %s%s' % (label, rc, out, err))
        return out
    def helper_run(operation, *values):
        cmd = 'env DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 python3 ' + shlex.quote(remote + '/trial_helper.py')
        return json.loads(run(cmd + ' ' + ' '.join(shlex.quote(str(v)) for v in (operation, *values)), operation))
    def free():
        owners = helper_run('owners')
        if owners:
            raise RuntimeError('Preserve DMA owner; do not program: ' + repr(owners))
    def identity(path, expected):
        actual = run('sha256sum ' + shlex.quote(path), 'identity').split()[0]
        if actual != expected:
            raise RuntimeError('Pinned identity mismatch: ' + path)
    def config(label):
        # Read-only samples; no governor, frequency, library or thermal writes.
        command = ('for f in /sys/devices/system/cpu/cpufreq/policy*/scaling_governor '
                   '/sys/devices/system/cpu/cpufreq/policy*/scaling_cur_freq '
                   '/sys/devices/system/cpu/cpufreq/policy*/scaling_min_freq '
                   '/sys/devices/system/cpu/cpufreq/policy*/scaling_max_freq '
                   '/sys/class/devfreq/*/governor /sys/class/devfreq/*/cur_freq '
                   '/sys/class/devfreq/*/min_freq /sys/class/devfreq/*/max_freq '
                   '/sys/class/thermal/thermal_zone*/type /sys/class/thermal/thermal_zone*/temp; '
                   'do if [ -r "$f" ]; then printf "%s=" "$f"; cat "$f"; fi; done')
        run(command, label)
    def program(restore=False):
        free()
        absent = run('if [ -e /sys/bus/pci/devices/0002:21:00.0 ]; then echo present; else echo absent; fi', 'endpoint').strip() == 'absent'
        flags = ['--restore-display30'] if restore else ['--batch']
        if absent:
            flags.append('--post-reboot')
        manifest['status'] = 'restoring_original' if restore else 'programming_batch'
        save()
        label = 'restore_program' if restore else 'batch_program'
        with (folder / (label + '.log')).open('w', encoding='utf-8') as log:
            rc = subprocess.call([sys.executable, str(staged / 'program_fpga.py'), *flags], cwd=staged,
                                 stdout=log, stderr=subprocess.STDOUT)
        if rc:
            raise RuntimeError(label + ' failed; endpoint state uncertain; preserve for recovery')
    try:
        run('mkdir ' + shlex.quote(remote) + ' && mkdir ' + shlex.quote(remote + '/cooperative_linux_transport') + ' ' + shlex.quote(remote + '/tmp'), 'mkdir', sudo=False)
        with client.open_sftp() as sftp:
            sftp.put(str(helper), remote + '/trial_helper.py')
            sftp.chmod(remote, 0o755)
            sftp.chmod(remote + '/trial_helper.py', 0o644)
            for source in sources:
                target = 'cooperative_linux_transport/driver_abi.hpp' if source == ABI else source.name
                sftp.put(str(source), remote + '/' + target)
        identity(MODEL, MODEL_SHA)
        identity(ACTIVE, VIEWER_SHA)
        identity(BACKUP, VIEWER_SHA)
        run('sha256sum /usr/lib/librknnrt.so; uname -a; ls -l /dev/pango_pci_driver; '
            'readlink /sys/bus/pci/devices/0002:21:00.0/driver', 'environment')
        run('if pgrep -x make || pgrep -x cc1plus || pgrep -x ld; then exit 2; fi', 'no_existing_build')
        owners = helper_run('owners')
        if (len(owners) != 1 or owners[0]['pid'] != args.viewer_pid or owners[0]['exe'] != ACTIVE or
                owners[0]['sha256'] != VIEWER_SHA or owners[0]['state'] in ('T', 't', 'Z', 'D')):
            raise RuntimeError('Unexpected viewer owner/state; no shutdown attempted: ' + repr(owners))
        viewer = owners[0]
        manifest['original_owner'] = viewer
        for shared in (False, True):
            binary = 'paired_shared' if shared else 'paired_pointer'
            command = ('cd ' + shlex.quote(remote) + ' && env TMPDIR=' + shlex.quote(remote + '/tmp') + ' g++ -std=c++17 -O2 -Wall -Wextra -Werror ' +
                       ('-DOFFLOAD_SHARED_INPUT ' if shared else '') +
                       'paired_pointer.cpp -lrknnrt -pthread -o ' + binary + ' && chmod 755 ' + binary +
                       ' && sha256sum ' + binary)
            run(command, 'build_' + binary, timeout=120, sudo=False)
        config('config_before')
        manifest['status'] = 'graceful_quit'
        save()
        manifest['quit_receipt'] = helper_run('quit', args.viewer_pid, viewer['starttime'], VIEWER_SHA, args.quit_key)
        deadline = time.monotonic() + 30
        while True:
            retired = helper_run('retired', args.viewer_pid, viewer['starttime'])
            if retired['retired'] and not retired['owners']:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError('Viewer did not retire in 30 seconds; preserve owner; no signal fallback')
            time.sleep(1)
        program()
        manifest['summaries'] = {}
        for shared in (False, True):
            free()
            binary = 'paired_shared' if shared else 'paired_pointer'
            manifest['status'] = 'running_' + binary
            save()
            config('config_before_' + binary)
            command = ' '.join(shlex.quote(v) for v in (remote + '/' + binary, MODEL, '10', '240'))
            # On SSH timeout the process may still own DMA. Do not kill or restore.
            rc, out, err = board_ssh.run(client, command + ' >' + shlex.quote(remote + '/' + binary + '.jsonl') +
                                        ' 2>' + shlex.quote(remote + '/' + binary + '.stderr'), sudo=True, timeout=600)
            with client.open_sftp() as sftp:
                for suffix in ('.jsonl', '.stderr'):
                    sftp.get(remote + '/' + binary + suffix, str(folder / (binary + suffix)))
            if rc:
                raise RuntimeError(binary + ' failed; preserve possibly quarantined owner: ' + out + err)
            manifest['summaries'][binary] = summarize_pairs((folder / (binary + '.jsonl')).read_text(), 240, shared)
            free()
            config('config_after_' + binary)
            save()
        config('config_after')
        program(restore=True)
        identity(ACTIVE, VIEWER_SHA)
        # Launch the unchanged original binary: no overwrite of active/backup.
        remote_log = remote + '/restored_acceptance.log'
        free()
        command = ('cd /userdata/detview-hdmifull || exit 2\nsetsid nohup env DISPLAY=:0 '
                   'XAUTHORITY=/var/run/lightdm/root/:0 QT_QPA_PLATFORM=xcb QT_XCB_GL_INTEGRATION=xcb_egl '
                   'DET_BENCH=1 ' + shlex.quote(ACTIVE) + ' --model MVP_accuracy_round1 --fullscreen >' +
                   shlex.quote(remote_log) + ' 2>&1 </dev/null & echo $!')
        pid = int(run(command, 'restart_viewer').strip())
        # Shell async-list PID can precede exec; find the actual sole device owner.
        for attempt in range(30):
            owners = helper_run('owners')
            if owners:
                break
            time.sleep(1)
        if len(owners) != 1 or owners[0]['exe'] != ACTIVE or owners[0]['sha256'] != VIEWER_SHA:
            raise RuntimeError('Original viewer did not become verified sole owner')
        restored = owners[0]
        manifest.update(status='original_viewer_health', launch_pid=pid, restored_owner=restored, remote_log=remote_log)
        save()
        for attempt in range(19):
            time.sleep(5)
            current = helper_run('process', restored['pid'])
            if (current['starttime'] != restored['starttime'] or current['sha256'] != VIEWER_SHA or
                    current['state'] in ('T', 't', 'Z', 'D')):
                raise RuntimeError('Restored viewer stopped or identity changed')
        with client.open_sftp() as sftp:
            sftp.get(remote_log, str(folder / 'restored_acceptance.log'))
        owners = helper_run('owners')
        if len(owners) != 1 or owners[0]['pid'] != restored['pid'] or owners[0]['starttime'] != restored['starttime']:
            raise RuntimeError('Restored viewer lost sole device ownership during health capture')
        after = viewer_metrics((folder / 'restored_acceptance.log').read_text(encoding='utf-8', errors='replace'))
        ratios = {key: after[key] / baseline[key] for key in ('new_paint_fps', 'swap_fps', 'npu_completed_fps')}
        ratios.update({'camera_' + key: after['cameras'][key] / baseline['cameras'][key] for key in baseline['cameras']})
        manifest.update(restored_metrics=after, restored_baseline_ratios=ratios, min_fps_ratio=args.min_fps_ratio)
        if min(ratios.values()) < args.min_fps_ratio:
            raise RuntimeError('Original viewer FPS below configured baseline ratio; preserve running viewer for diagnosis')
        manifest['status'] = 'complete'
        save()
        print(json.dumps(manifest, indent=2))
        print('Evidence:', folder)
        return 0
    except BaseException as error:
        manifest['failed_phase'] = manifest['status']
        manifest.update(status='aborted_preserve_board', error=str(error))
        save()
        print('ABORTED: board state preserved; no forced shutdown or automatic programming. Evidence: ' + str(folder), file=sys.stderr)
        raise
    finally:
        client.close()


if __name__ == '__main__':
    raise SystemExit(main())
