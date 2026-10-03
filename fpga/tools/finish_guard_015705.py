"""Single-owner, durable authorized 50K guard build/burn/board workflow."""
import json
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
ARCHIVE = build.ROOT / 'bitstream_final_50k_20261003_015705'
EVIDENCE = ROOT / 'log/six_guard_board_20261003'
HANDOFF = ROOT / 'log/six_guard_015705_handoff.json'
BIN = build.BIN
EVIDENCE.mkdir(exist_ok=True)
state = {'pid': os.getpid(), 'script': str(Path(__file__).resolve()),
         'archive': str(ARCHIVE), 'evidence': str(EVIDENCE),
         'scope': '50K only; no 100H build or production IP edits',
         'rollback_bit': str(build.ROOT / 'bitstream_final_50k_20261003_010300/hdmi_ddr_ov5640_top.sbit')}

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
        code = stdout.channel.recv_exit_status()
        if code:
            raise RuntimeError(f'RK command failed {code}: {err.decode(errors="replace")}')
        return out
    finally:
        cli.close()

def run_tool(name, args, timeout=100):
    with (EVIDENCE / (name + '.log')).open('wb') as stream:
        return subprocess.run([sys.executable, *map(str, args)], cwd=ROOT,
                              stdout=stream, stderr=subprocess.STDOUT, timeout=timeout).returncode

def close_window(pid):
    subprocess.run(['powershell', '-NoProfile', '-Command',
                    f'$guardWindow=Get-Process -Id {pid} -ErrorAction SilentlyContinue; if ($guardWindow) {{ $guardWindow.CloseMainWindow() }}'],
                   capture_output=True, timeout=10)

def cfg(name, tcl, success, timeout):
    log = EVIDENCE / (name + '.log')
    with log.open('wb') as output, (EVIDENCE / (name + '.err')).open('wb') as error:
        proc = subprocess.Popen([str(BIN / 'cdt_cfg.exe'), '-ip', '127.0.0.1', '-port', '65425', '-file', str(tcl)],
                                stdout=output, stderr=error, cwd=ROOT / 'project')
        stage(name, cfg_pid=proc.pid)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            text = log.read_bytes().decode('gb18030', errors='replace')
            if success(text):
                close_window(proc.pid)
                for _ in range(20):
                    if proc.poll() is not None:
                        break
                    time.sleep(0.5)
                if proc.poll() is None:
                    raise RuntimeError(f'{name} succeeded but window remains open PID {proc.pid}; no process killed')
                return text
            if proc.poll() is not None:
                raise RuntimeError(f'{name} exited {proc.returncode} without success: {log}')
            time.sleep(0.5)
        raise RuntimeError(f'{name} timeout; PID {proc.pid} left untouched, never stop active programming')

def main():
    # Exclusive persistent lock prevents a second programming workflow.
    lock = EVIDENCE / 'autorunner.lock'
    with lock.open('x') as stream:
        stream.write(str(os.getpid()))
    stage('waiting_build', status='running')
    deadline = time.monotonic() + 7200
    while True:
        status = load('status.json')
        if status['status'] == 'complete':
            break
        if status['status'] == 'blocked':
            raise RuntimeError('Build blocked: ' + status.get('blocker', 'unknown'))
        if time.monotonic() >= deadline:
            raise RuntimeError('Build did not finish within two hours; no programming started')
        time.sleep(15)
    stage('checking_build_gates')
    if not status.get('source_inputs_unchanged') or not status.get('physical_audit_passed'):
        raise RuntimeError('Missing source/physical gate')
    build.check_inputs(ARCHIVE)
    for name in ('final_sta_proof.json', 'physical_original_proof.json', 'physical_audited_proof.json', 'constraints_preserved.json'):
        if load(name)['problems']:
            raise RuntimeError('Gate problems: ' + name)
    sta = load('final_sta_proof.json')
    if not sta['summary_rows'] or any(row['failing'] or row['slack'] < 0 for row in sta['summary_rows']):
        raise RuntimeError('STA is not zero failing endpoints')
    audited = ARCHIVE / 'audited_route/hdmi_ddr_ov5640_top_pnr.adf'
    report = ARCHIVE / 'final_sta/report_timing/hdmi_ddr_ov5640_top.rtr'
    if build.sha(audited) != status['audited_route_sha256'] or build.sha(report) != status['report_sha256']:
        raise RuntimeError('Exact route/report SHA mismatch')
    build.prove_report(ARCHIVE, report, audited)
    build.prove_physical_preserved(ARCHIVE)
    original = ARCHIVE / 'original_full_route/hdmi_ddr_ov5640_top_pnr.adf'
    if build.sha(original) != status['original_route_sha256']:
        raise RuntimeError('Original route SHA mismatch')
    if load('physical_audited_proof.json')['db_sha256'] != build.sha(audited):
        raise RuntimeError('Physical proof is not exact audited route')
    bit = Path(status['bitstream'])
    if bit.parent != ARCHIVE or build.sha(bit) != status['bit_sha256']:
        raise RuntimeError('Bit SHA/path mismatch')
    if processes():
        raise RuntimeError('Vendor/JTAG processes still active; no competing server started: ' + processes())
    stage('starting_jtag_server', bit_sha256=build.sha(bit), bitstream=str(bit))
    with (EVIDENCE / 'jtag_server.log').open('wb') as output, (EVIDENCE / 'jtag_server.err').open('wb') as error:
        server = subprocess.Popen([str(BIN / 'cdt_js.exe'), '-port', '65425'], stdout=output, stderr=error)
    stage('jtag_server_started', server_pid=server.pid)
    time.sleep(4)
    scan = cfg('jtag_scan', ROOT / 'project/scan_six_100h_20261002.tcl',
               lambda text: 'Executing : cfg_scan_chain successfully.' in text, 90)
    devices = re.findall(r'^\s*(P(?:G|GL)[A-Za-z0-9_-]+)\s*$', scan, re.M)
    if devices != ['PGL50H']:
        raise RuntimeError('Scan must contain exactly PGL50H: ' + repr(devices))
    build.check_inputs(ARCHIVE)
    if build.sha(bit) != status['bit_sha256']:
        raise RuntimeError('Bit changed before burn')
    cfg('jtag_flash', ROOT / 'project/flash_50k_guard_20261003_015705.tcl',
        lambda text: 'The Progress:' in text and '100%' in text and 'The done bit is 1' in text
        and 'COMMAND[Program] execute successfully' in text, 300)
    if build.sha(bit) != status['bit_sha256']:
        raise RuntimeError('Bit changed during burn')
    stage('burn_verified', actual_last_burn_sha256=status['bit_sha256'])
    build.save(EVIDENCE / 'actual_last_burn.json', {'sha256': status['bit_sha256'], 'bitstream': str(bit),
               'scan_device': 'PGL50H', 'success_log': str(EVIDENCE / 'jtag_flash.log')})
    server.terminate()  # Only after successful programming and cfg window exit.
    failures = []
    try:
        stage('stopping_viewer')
        remote("pkill -f '^/bin/bash /root/ov5640/run_camview.sh' || true; pkill -x camview || true")
        stage('board_verification')
        code = run_tool('verification', [TOOLS / 'verify_six_image.py', '--label', 'six_guard_board_20261003', '--seconds', '30', '--cam1-delay', '140'], 110)
        if code:
            failures.append(f'30s stream verifier exit {code}')
        # A second diagnostic sample set bounds the 30s acceptance interval.
        final = remote('python3 /tmp/read_sfp_diagnostics.py')
        (EVIDENCE / 'diagnostics_after.jsonl').write_bytes(final)
        first = [json.loads(line) for line in (EVIDENCE / 'board.jsonl').read_text().splitlines() if line.startswith('{')]
        before = [row for row in first if 'cameras' in row]
        after = [json.loads(line) for line in final.decode().splitlines() if line.startswith('{')]
        if not before or not after:
            failures.append('Missing interval diagnostic evidence')
        else:
            for index in range(2):
                rows = [row['cameras'][index] for row in before + after]
                if any(row['input_pixels'] != 307200 for row in rows):
                    failures.append(f'CAM{index+5} input count not consistently 307200')
                if any(row['short_count'] != rows[0]['short_count'] for row in rows):
                    failures.append(f'CAM{index+5} short count increased')
        code = run_tool('geometry', [TOOLS / 'check_sensor_colorbars.py', EVIDENCE / 'cam5.rgb565', EVIDENCE / 'cam6.rgb565', '--output', EVIDENCE / 'colorbar_geometry.json'])
        if code:
            failures.append(f'Colorbar geometry check exit {code}')
    except Exception as error:
        failures.append(str(error))
    finally:
        stage('restoring_viewer', verification_failures=failures)
        remote('nohup /bin/bash /root/ov5640/run_camview.sh >/root/ov5640/camview_guard.log 2>&1 </dev/null &')
        time.sleep(8)
        viewer = remote('pgrep -af run_camview.sh; pgrep -x camview')
        (EVIDENCE / 'viewer_processes.txt').write_bytes(viewer)
        code = run_tool('screenshot', [TOOLS / 'capture_rk3568_screen.py', '--output', EVIDENCE / 'rk3568_guard_screen.png'], 45)
        if code:
            failures.append(f'Actual X11 screenshot capture exit {code}')
    result = {'pass': not failures, 'failures': failures, 'actual_last_burn_sha256': status['bit_sha256'],
              'evidence': str(EVIDENCE), 'root_ctc_proven': False,
              'next_50k_step_if_failed': 'Compare guard-only against guard plus dedicated blanking skip/burst scheduling using saved count and geometry evidence; no 100H build.'}
    build.save(EVIDENCE / 'workflow_result.json', result)
    stage('finished', status='verified' if not failures else 'board_acceptance_failed', result=result)
    with (ROOT / 'log/six_repair_20261002.md').open('a', encoding='utf8') as stream:
        stream.write('\n\n015705 durable autorunner result: ' + json.dumps(result) + '\n')
    return 0 if not failures else 2

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        stage('blocked', status='blocked', blocker=str(error))
        traceback.print_exc()
        sys.exit(1)
