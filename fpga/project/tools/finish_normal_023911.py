"""Durable single-owner 50K normal-image flash and evidence workflow."""
import json
import argparse
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import traceback
import build_50k_final as build
from board_host import ssh_connect

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / 'project/tools'
parser = argparse.ArgumentParser()
parser.add_argument('--archive', type=Path, default=build.ROOT / 'bitstream_final_50k_20261003_023911')
parser.add_argument('--baseline', type=Path, default=build.ROOT / 'bitstream_final_50k_20261003_015705')
parser.add_argument('--evidence', type=Path, default=ROOT / 'log/six_normal_guard_board_20261003')
parser.add_argument('--handoff', type=Path, default=ROOT / 'log/six_normal_023911_handoff.json')
parser.add_argument('--flash-tcl', type=Path, default=ROOT / 'project/flash_50k_normal_20261003_023911.tcl')
parser.add_argument('--margin-candidate', action='store_true')
parser.add_argument('--fps-guard', action='store_true')
parser.add_argument('--fps40', action='store_true')
parser.add_argument('--baseline-evidence', type=Path, default=ROOT / 'log/six_normal_guard_board_20261003')
options = parser.parse_args()
ARCHIVE, GUARD, EVIDENCE, HANDOFF = options.archive.resolve(), options.baseline.resolve(), options.evidence.resolve(), options.handoff.resolve()
EVIDENCE.mkdir(exist_ok=True)
state = {'pid': os.getpid(), 'script': str(Path(__file__).resolve()), 'archive': str(ARCHIVE),
         'evidence': str(EVIDENCE), 'scope': '50K only; no 100H build or production IP edits',
         'rollback_bit': str(GUARD / 'hdmi_ddr_ov5640_top.sbit'),
          'rollback_sha256': build.sha(GUARD / 'hdmi_ddr_ov5640_top.sbit')}

def stage(name, **values):
    state.update(stage=name, updated=time.strftime('%Y-%m-%d %H:%M:%S'), **values)
    build.save(HANDOFF, state)
    print(json.dumps(state), flush=True)

def load(name):
    return json.loads((ARCHIVE / name).read_text())

def processes():
    command = "Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^(pds|pds_shell|pnr|ta|bitgen|cdt_js|cdt_cfg)$' } | Select-Object Id,ProcessName | ConvertTo-Json -Compress"
    return subprocess.check_output(['powershell', '-NoProfile', '-Command', command], text=True).strip()

def remote(command):
    cli = ssh_connect(timeout=8)
    try:
        stdin, stdout, stderr = cli.exec_command('sudo -S bash -c ' + shlex.quote(command), timeout=35)
        stdin.write('123456\n'); stdin.flush()
        out, err = stdout.read(), stderr.read()
        if stdout.channel.recv_exit_status():
            raise RuntimeError('RK command failed: ' + err.decode(errors='replace'))
        return out
    finally:
        cli.close()

def run_tool(name, args, timeout=110):
    with (EVIDENCE / (name + '.log')).open('wb') as stream:
        return subprocess.run([sys.executable, *map(str, args)], cwd=ROOT,
                              stdout=stream, stderr=subprocess.STDOUT, timeout=timeout).returncode

def cfg(name, tcl, success, timeout):
    log = EVIDENCE / (name + '.log')
    with log.open('wb') as output, (EVIDENCE / (name + '.err')).open('wb') as error:
        proc = subprocess.Popen([str(build.BIN / 'cdt_cfg.exe'), '-ip', '127.0.0.1', '-port', '65425', '-file', str(tcl)],
                                stdout=output, stderr=error, cwd=ROOT / 'project')
        stage(name, cfg_pid=proc.pid)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            text = log.read_bytes().decode('gb18030', errors='replace')
            if success(text):
                subprocess.run(['powershell', '-NoProfile', '-Command',
                                '$normalWindow=Get-Process -Id %d -ErrorAction SilentlyContinue; if ($normalWindow) { $normalWindow.CloseMainWindow() }' % proc.pid],
                               capture_output=True, timeout=10)
                for _ in range(20):
                    if proc.poll() is not None:
                        break
                    time.sleep(0.5)
                if proc.poll() is None:
                    raise RuntimeError(name + ' succeeded but window remains open; process left untouched')
                stage(name + '_window_exited', cfg_exit_code=proc.returncode)
                return text
            if proc.poll() is not None:
                raise RuntimeError(name + ' exited without success: ' + str(log))
            time.sleep(0.5)
        raise RuntimeError('%s timeout; never stop active programming PID %d' % (name, proc.pid))

def source_gate():
    build.check_inputs(ARCHIVE)
    current = load('input_sha256.json')
    old = json.loads((GUARD / 'input_sha256.json').read_text())
    changed = [n for n in sorted(current.keys() | old.keys()) if current.get(n) != old.get(n)]
    expected_change = ('source/rtl/cam2_merge.v' if options.fps_guard else
                       'source/rtl/reg_config.v' if options.margin_candidate else 'source/rtl/hdmi_ddr_ov5640_top.v')
    expected_changes = (['source/rtl/cam2_merge.v', 'source/rtl/reg_config.v']
                        if options.fps40 else [expected_change])
    if changed != expected_changes:
        raise RuntimeError('Unexpected source changes: ' + repr(changed))
    if options.fps40:
        candidate = load('fps40_candidate.json')
        for name in expected_changes:
            if current[name] != candidate['candidate_hashes'][name] or old[name] != candidate['baseline_hashes'][name]:
                raise RuntimeError('FPS40 candidate/rollback source hash mismatch')
        if state['rollback_sha256'] != candidate['rollback_sha256']:
            raise RuntimeError('FPS40 rollback bit mismatch')
    if options.fps_guard:
        candidate = load('candidate.json')
        if current[expected_change] != candidate['candidate_sha256'] or old[expected_change] != candidate['baseline_sha256']:
            raise RuntimeError('FPS guard candidate/rollback hash mismatch')
        if state['rollback_sha256'] != '99e4a240962915e80c3d9c045a7787e219e346e494f20f9f2478b3605627a384':
            raise RuntimeError('FPS guard rollback is not the accepted033106 bit')
    if options.margin_candidate and current[expected_change] != '1cd4405242a95f054fec9b7dd1e3ec7b84a46f5a5d15a02fad9a6902534e7124':
        raise RuntimeError('Margin candidate SHA mismatch')
    if options.margin_candidate and state['rollback_sha256'] != '1df94407f27a81bfa963be9c0e7f89a3d44ef6ac295680d26aafb66884fdcf5e':
        raise RuntimeError('Normal rollback SHA mismatch')
    if not re.search(rb'parameter\s+COLOR_BAR_TEST\s*=\s*0\s*,', (build.ROOT / 'source/rtl/hdmi_ddr_ov5640_top.v').read_bytes()):
        raise RuntimeError('Normal sensor configuration missing')
    if build.sha(GUARD / 'hdmi_ddr_ov5640_top.sbit') != state['rollback_sha256']:
        raise RuntimeError('Verified guard rollback changed')

def frame_evidence(report):
    from PIL import Image
    import numpy as np
    results = []
    for camera in (5, 6):
        item = next(row for row in report['results'] if row['camera'] == camera)
        raw = (EVIDENCE / ('cam%d.rgb565' % camera)).read_bytes()
        if len(raw) != 614400:
            raise RuntimeError('CAM%d incomplete raw frame' % camera)
        pixels = np.frombuffer(raw, dtype='<u2').reshape(480, 640)
        rgb = np.stack((((pixels >> 11) & 31) * 255 // 31,
                        ((pixels >> 5) & 63) * 255 // 63,
                        (pixels & 31) * 255 // 31), axis=-1).astype('uint8')
        Image.fromarray(rgb).save(EVIDENCE / ('cam%d.png' % camera))
        differences = np.abs(np.diff(rgb.astype('float32'), axis=0)).mean(axis=(1, 2))
        result = dict(item, raw_bytes=len(raw), unique_pixels=int(np.unique(pixels).size),
                       row_difference_max=float(differences.max()), row_difference_median=float(np.median(differences)))
        result['pixels'] = int(pixels.size)
        result['columns_632_639'] = []
        for column in range(632,640):
            values, counts = np.unique(pixels[:,column], return_counts=True)
            order = np.argsort(counts)[::-1][:8]
            result['columns_632_639'].append({'column':column, 'top_rgb565':
                [{'value':f'{int(values[k]):04X}', 'count':int(counts[k])} for k in order],
                'A534':int((pixels[:,column] == 0xa534).sum()), '8410':int((pixels[:,column] == 0x8410).sum())})
        if options.margin_candidate:
            baseline_raw = (options.baseline_evidence / ('cam%d.rgb565' % camera)).read_bytes()
            if len(baseline_raw) != 614400:
                raise RuntimeError('Incomplete baseline frame')
            baseline_pixels = np.frombuffer(baseline_raw, dtype='<u2').reshape(480,640)
            result['baseline_columns_632_639'] = []
            for column in range(632,640):
                values, counts = np.unique(baseline_pixels[:,column], return_counts=True)
                order = np.argsort(counts)[::-1][:8]
                result['baseline_columns_632_639'].append({'column':column, 'top_rgb565':
                    [{'value':f'{int(values[k]):04X}', 'count':int(counts[k])} for k in order],
                    'A534':int((baseline_pixels[:,column] == 0xa534).sum()),
                    '8410':int((baseline_pixels[:,column] == 0x8410).sum())})
            result['baseline_raw_path'] = str(options.baseline_evidence / ('cam%d.rgb565' % camera))
            result['baseline_raw_sha256'] = build.sha(options.baseline_evidence / ('cam%d.rgb565' % camera))
        if result['unique_pixels'] <= 1:
            raise RuntimeError('CAM%d uniformly invalid frame' % camera)
        results.append(result)
    build.save(EVIDENCE / 'normal_frame_metrics.json', results)
    return results

def main():
    with (EVIDENCE / 'autorunner.lock').open('x') as stream:
        stream.write(str(os.getpid()))
    source_gate()
    stage('waiting_build', status='running')
    deadline = time.monotonic() + 7200
    while True:
        status = load('status.json')
        if status['status'] == 'complete':
            break
        if status['status'] == 'blocked':
            raise RuntimeError('Build blocked: ' + status.get('blocker', 'unknown'))
        if time.monotonic() >= deadline:
            raise RuntimeError('Build did not finish within two hours')
        time.sleep(15)
    stage('checking_build_gates')
    source_gate()
    if not status.get('source_inputs_unchanged') or not status.get('physical_audit_passed'):
        raise RuntimeError('Missing source/physical gate')
    for name in ('final_sta_proof.json', 'physical_original_proof.json', 'physical_audited_proof.json', 'constraints_preserved.json'):
        if load(name)['problems']:
            raise RuntimeError('Gate problems: ' + name)
    sta = load('final_sta_proof.json')
    if not sta['summary_rows'] or any(row['failing'] or row['slack'] < 0 for row in sta['summary_rows']):
        raise RuntimeError('STA is not zero failing endpoints')
    audited = ARCHIVE / 'audited_route/hdmi_ddr_ov5640_top_pnr.adf'
    report_path = ARCHIVE / 'final_sta/report_timing/hdmi_ddr_ov5640_top.rtr'
    if build.sha(audited) != status['audited_route_sha256'] or build.sha(report_path) != status['report_sha256']:
        raise RuntimeError('Exact route/report SHA mismatch')
    build.prove_report(ARCHIVE, report_path, audited)
    build.prove_physical_preserved(ARCHIVE)
    if build.sha(ARCHIVE / 'original_full_route/hdmi_ddr_ov5640_top_pnr.adf') != status['original_route_sha256']:
        raise RuntimeError('Original route SHA mismatch')
    if load('physical_audited_proof.json')['db_sha256'] != build.sha(audited):
        raise RuntimeError('Physical proof is not exact audited route')
    bit = Path(status['bitstream'])
    if bit.parent != ARCHIVE or build.sha(bit) != status['bit_sha256']:
        raise RuntimeError('Bit SHA/path mismatch')
    busy = processes()
    if busy:
        raise RuntimeError('Vendor/JTAG processes still active: ' + busy)
    stage('starting_jtag_server', bit_sha256=build.sha(bit), bitstream=str(bit))
    with (EVIDENCE / 'jtag_server.log').open('wb') as output, (EVIDENCE / 'jtag_server.err').open('wb') as error:
        server = subprocess.Popen([str(build.BIN / 'cdt_js.exe'), '-port', '65425'], stdout=output, stderr=error)
    stage('jtag_server_started', server_pid=server.pid)
    time.sleep(4)
    scan = cfg('jtag_scan', ROOT / 'project/scan_six_100h_20261002.tcl',
               lambda text: 'Executing : cfg_scan_chain successfully.' in text, 90)
    devices = re.findall(r'^\s*(P(?:G|GL)[A-Za-z0-9_-]+)\s*$', scan, re.M)
    if devices != ['PGL50H']:
        raise RuntimeError('Scan must contain exactly PGL50H: ' + repr(devices))
    source_gate()
    if build.sha(bit) != status['bit_sha256']:
        raise RuntimeError('Bit changed before burn')
    tcl = options.flash_tcl.resolve()
    expected = 'cfg_scan_chain\ncfg_assign_file -file %s -device_index 0\ncfg_program -device_index 0\n' % bit.as_posix()
    if tcl.read_text() != expected:
        raise RuntimeError('Flash Tcl does not match exact normal archive')
    cfg('jtag_flash', tcl, lambda text: 'The Progress:' in text and '100%' in text
        and 'The done bit is 1' in text and 'COMMAND[Program] execute successfully' in text, 300)
    if build.sha(bit) != status['bit_sha256']:
        raise RuntimeError('Bit changed during burn')
    stage('burn_verified', actual_last_burn_sha256=status['bit_sha256'])
    build.save(EVIDENCE / 'actual_last_burn.json', {'sha256': status['bit_sha256'], 'bitstream': str(bit),
               'scan_device': 'PGL50H', 'success_log': str(EVIDENCE / 'jtag_flash.log')})
    server.terminate()
    server.wait(timeout=10)
    failures, frames = [], []
    try:
        stage('stopping_viewer')
        remote("pkill -f '^/bin/bash /root/ov5640/run_camview.sh' || true; pkill -x camview || true")
        stage('board_verification')
        if run_tool('verification', [TOOLS / 'verify_six_normal_image.py', '--label', EVIDENCE.name, '--seconds', '30', '--cam1-delay', '140']):
            failures.append('30s stream verifier failed')
        final = remote('python3 /tmp/read_sfp_diagnostics.py')
        (EVIDENCE / 'diagnostics_after.jsonl').write_bytes(final)
        rows = [json.loads(line) for line in (EVIDENCE / 'board.jsonl').read_text().splitlines() + final.decode().splitlines() if line.startswith('{')]
        before_after = [row for row in rows if 'cameras' in row]
        during = [json.loads(line) for line in (EVIDENCE / 'diagnostics_during.jsonl').read_text().splitlines() if line.startswith('{')]
        diagnostics = sorted(before_after + during, key=lambda row: row['time'])
        if len(before_after) < 20 or len(during) < 50 or during[-1]['time'] - during[0]['time'] < 29:
            failures.append('Missing before/after diagnostic evidence')
        else:
            for index in range(2):
                camera_rows = [row['cameras'][index] for row in diagnostics]
                if any(row['input_pixels'] != 307200 for row in camera_rows):
                    failures.append('CAM%d input count not consistently 307200' % (index + 5))
                if any(row['short_count'] != camera_rows[0]['short_count'] for row in camera_rows):
                    failures.append('CAM%d short count increased' % (index + 5))
                if any(row['overflow'] for row in camera_rows):
                    failures.append('CAM%d overflow mask set' % (index + 5))
                if any((int(row['fault'], 16) & 0xf0000000) & ~(int(camera_rows[0]['fault'], 16) & 0xf0000000) for row in camera_rows):
                    failures.append('CAM%d fresh fault bit asserted' % (index + 5))
            build.save(EVIDENCE / 'diagnostic_interval.json', {'samples': diagnostics,
                       'sticky_dma_policy': 'Old unchanged DMA/tag bits are snapshots, not fresh faults; acceptance requires continuous fresh frame tags.'})
        report = json.loads((EVIDENCE / 'report.json').read_text())
        if report['duration'] < 30 or len(report['results']) != 6 or not report['pass']:
            failures.append('Incomplete six-camera freshness acceptance')
        for camera in (5, 6):
            item = next(row for row in report['results'] if row['camera'] == camera)
            if not item['pass'] or item['rate'] <= 0 or not item['capture'] or item['capture']['tag'] <= 0:
                failures.append('CAM%d missing fresh captured frame' % camera)
            if options.fps40 and item['rate'] < 40:
                failures.append('CAM%d true tag rate below40fps: %.4f' % (camera,item['rate']))
        frames = frame_evidence(report)
    except Exception as error:
        failures.append(str(error))
    finally:
        stage('restoring_viewer', verification_failures=failures)
        try:
            if options.fps_guard or options.fps40:
                remote('nohup sh -c "cd /root/ov5640/camview_fps_candidate && '
                       'DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 exec ./camview" '
                       '>/root/ov5640/camview_fps_candidate.log 2>&1 </dev/null &')
            else:
                remote('nohup /bin/bash /root/ov5640/run_camview.sh >/root/ov5640/camview_normal.log 2>&1 </dev/null &')
            time.sleep(8)
            (EVIDENCE / 'viewer_processes.txt').write_bytes(remote('pgrep -af run_camview.sh || true; pgrep -x camview'))
            if run_tool('screenshot', [TOOLS / 'capture_rk3568_screen.py', '--output', EVIDENCE / 'rk3568_normal_screen.png'], 45):
                failures.append('Actual X11 screenshot capture failed')
        except Exception as error:
            failures.append('Viewer/screenshot: ' + str(error))
    result = {'counts_tag_pass': not failures, 'needs_visual_review': True, 'objective_complete': False,
              'failures': failures, 'frames': frames, 'actual_last_burn_sha256': status['bit_sha256'],
              'evidence': str(EVIDENCE), 'normal_configuration': 'COLOR_BAR_TEST=0; dark scene expected; no colorbar geometry gate',
              'visual_review': 'Parent must read actual X11 screenshot and CAM5/6 PNG images; inspect scene correspondence and rows for obvious tearing.'}
    build.save(EVIDENCE / 'workflow_result.json', result)
    stage('finished', status='needs_visual_review' if not failures else 'board_acceptance_failed', result=result)
    with (ROOT / 'log/six_repair_20261002.md').open('a', encoding='utf8') as stream:
        stream.write('\n\n' + EVIDENCE.name + ' normal durable autorunner result: ' + json.dumps(result) + '\n')
    return 0 if not failures else 2

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        stage('blocked', status='blocked', blocker=str(error))
        traceback.print_exc()
        sys.exit(1)
