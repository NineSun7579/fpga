"""Fail-closed motion 100H programmer; --check never starts/connects vendor tools.

Build evidence contract: motion_100h/build.py's completed status.json, plus its
run/pin_audit.json, phy_audit.json, final_sta_proof.json and routed/top_pnr.adf.
--manifest defaults to --build-status; it must contain bit and bit_sha256.
Flash additionally requires --sram-receipt and --acceptance JSON containing
accepted: true, bit_sha256, sram_receipt_sha256, and a nonempty reviewer.
Acceptance is supplied by the parent AFTER runtime SRAM validation.
Logs/Tcl/receipt are retained in a unique directory. No image-name taskkill,
viewer/PCIe actions, automatic rollback, or flash promotion is performed.
If the vendor does not flush its documented cfg.log, the Tcl guard fails closed.
"""

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
import uuid

BIN = Path('C:/pango/PDS_2022.2-SP6.4/bin')
PORT = 65426
TARGET = 'PG2L100H'
ERROR = re.compile(r'^\s*E:|invalid command name|MOTION_GUARD:|\b(?:failed|failure)\b', re.M | re.I)
BASELINE = Path(__file__).resolve().parents[1] / 'bitstream_six_recovery_20261002_192245/top.sbit'
BASELINE_SHA256 = 'c3f07533e37e77ab734d37a5a4ba4ed8ebc8af0841e09fa43f2dcc076f16a44a'


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def tcl_word(value):
    # Quoted Tcl words escape substitution and quotes, including pathological paths.
    text = str(value).replace('\\', '/')
    require(not any(c in text for c in '\r\n\x00'), 'Invalid Tcl path')
    return '"' + ''.join('\\' + c if c in '$[]"\\{}' else c for c in text) + '"'


def evidence(args):
    bit = Path(args.bit)
    require(bit.is_absolute(), '--bit must be an absolute path')
    bit = bit.resolve(strict=True)
    require(bit.is_file() and bit.stat().st_size > 0, 'Empty/missing bitstream')
    status_path = Path(args.build_status).resolve(strict=True)
    status = load(status_path)
    manifest_path = Path(args.manifest or args.build_status).resolve(strict=True)
    manifest = load(manifest_path)
    digest = sha(bit)
    require(status.get('stage') == 'complete' and status.get('status') == 'complete',
            'Build status is not completed')
    for doc in (status, manifest):
        require(doc.get('bit_sha256', '').lower() == digest, 'Saved bit SHA256 mismatch')
        require(Path(doc.get('bit', '')).is_absolute() and
                Path(doc['bit']).resolve() == bit, 'Saved bit path mismatch')
    run = Path(status['run']).resolve(strict=True)
    require(bit.parent == run, 'Bit does not belong to completed build run')
    pin = load(run / 'pin_audit.json')
    phy = load(run / 'phy_audit.json')
    timing = load(run / 'final_sta_proof.json')
    resource = load(run / 'resource_proof.json')
    histories = resource.get('histories', [])
    require(resource.get('required_histories') == 4 and len(histories) == 4
            and {row.get('instance') for row in histories} == {
                prefix + '/u_motion_tap/u_detector' for prefix in
                ('ov5640_top', 'cam2_ov5640_top', 'cam3_ov5640_top', 'cam4_ov5640_top')}
            and all(row.get('depth') == 19200 and row.get('width') == 8
                    and row.get('mode') == 'read_first' and row.get('evidence')
                    and row.get('bram_instances') for row in histories),
            'Four local CAM1–4 mapped read-first histories missing from build evidence')
    route_hash = sha(run / 'routed/top_pnr.adf')
    provenance = load(run / 'bit_provenance.json')
    bound_files = {'resource_proof_sha256': run / 'resource_proof.json',
                   'pin_proof_sha256': run / 'pin_audit.json',
                   'phy_proof_sha256': run / 'phy_audit.json',
                   'input_manifest_sha256': run / 'input_sha256.json'}
    require(all(provenance.get(key) == sha(path) for key, path in bound_files.items()),
            'Bit generation proofs changed after final build')
    require(provenance.get('bit_sha256') == digest and
            provenance.get('route_sha256') == route_hash and
            provenance.get('mapped_sha256') == resource.get('mapped_sha256'),
            'Bit generation is not bound to the reviewed map and route')
    require(pin.get('identical') is True and pin.get('ports', 0) >= 100,
            'Pin gate incomplete')
    require(pin.get('report_sha256') == sha(run / 'routed/top_prr.prt'), 'Pin report changed')
    require(phy.get('identical') is True and bool(phy.get('actual')),
            'Dedicated PHY/route gate incomplete')
    require(all(doc.get('route_sha256') == route_hash for doc in (status, phy, timing)),
            'Route evidence mismatch')
    report_hash = sha(run / 'final_sta/report_timing/top.rtr')
    require(provenance.get('report_sha256') == report_hash, 'Bit generation timing hash mismatch')
    require(status.get('report_sha256') == report_hash == timing.get('report_sha256'),
            'Timing report changed')
    rows = timing.get('rows', [])
    expected = {(kind, corner) for kind in ('Setup', 'Hold', 'Recovery', 'Removal', 'Minimum Pulse Width')
                for corner in ('Slow', 'Fast')}
    require(expected <= {tuple(row.get('section', [])) for row in rows} and
            all(isinstance(row.get('slack'), (int, float)) and row['slack'] >= 0 for row in rows),
            'Completed multi-corner timing gates missing')
    report_path = run / 'final_sta/report_timing/top.rtr'
    with report_path.open('rb') as stream:
        report = stream.read(262144).decode('gb18030', errors='replace')
    require(all(token in report for token in ('Timing Models: Production',
            'Timing analysis mode : multi corner', 'Design Summary : All Constraints Met.'))
             and 'Slack (VIOLATED)' not in report, 'Final timing report not passing')
    with report_path.open('rb') as stream:
        overlap = b''
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            block = overlap + chunk
            require(b'Slack (VIOLATED)' not in block, 'Final timing report contains a violated path')
            overlap = block[-32:]
    if args.mode == 'flash':
        require(args.sram_receipt and args.acceptance,
                'Flash requires successful --sram-receipt and parent --acceptance')
        receipt = load(args.sram_receipt)
        acceptance = load(args.acceptance)
        require(receipt.get('status') == 'success' and receipt.get('mode') == 'sram'
                and receipt.get('target') == TARGET and receipt.get('bit_sha256') == digest
                and receipt.get('stages', {}).get('device_done') is True
                and receipt.get('stages', {}).get('program_success') is True,
                'Successful SRAM programming receipt missing/mismatched')
        require(acceptance.get('accepted') is True and acceptance.get('reviewer')
                and acceptance.get('bit_sha256') == digest
                and acceptance.get('sram_receipt_sha256') == sha(args.sram_receipt),
                'Parent SRAM runtime acceptance missing/mismatched')
    return bit, digest, {'build_status': str(status_path), 'build_status_sha256': sha(status_path),
                         'manifest': str(manifest_path), 'manifest_sha256': sha(manifest_path),
                         'route_sha256': route_hash, 'timing_report_sha256': report_hash}


def scan_guard(log):
    # cfg_scan_chain has no proven machine-readable return value. Use the proven
    # primary log (not duplicated debug logs), and require a single device line.
    return '''cfg_scan_chain
set motion_log [open %s r]
set motion_text [read $motion_log]
close $motion_log
set motion_start [string last "Executing : cfg_scan_chain\\n" $motion_text]
if {$motion_start < 0} {error "MOTION_GUARD: scan log format not established"}
set motion_scan [string range $motion_text $motion_start end]
if {[string first "Executing : cfg_scan_chain successfully." $motion_scan] < 0} {
    error "MOTION_GUARD: scan has not completed successfully"
}
set motion_devices [regexp -all -inline -line {^PG[A-Z0-9]+(?:-[A-Za-z0-9]+)?\\r?$} $motion_scan]
set motion_device_count [regexp -all {This device configure situation \\(done bit\\):} $motion_scan]
if {[llength $motion_devices] != 1 || $motion_device_count != 1 || [string trim [lindex $motion_devices 0]] ne "PG2L100H"} {
    error "MOTION_GUARD: expected exactly one PG2L100H, got $motion_devices"
}
''' % tcl_word(log)


def script(bit, mode, log):
    text = scan_guard(log)
    if mode == 'sram':
        text += ('cfg_assign_file -file %s -device_index 0\n'
                 'cfg_program -device_index 0\n') % tcl_word(bit)
    else:
        text += ('cfg_set_cable_property -index 0 -freq 1MHz\n'
                   'cfg_jtag_flash_scan_device -device_index 0\n'
                   'cfg_jtag_flash_assign_file -file %s -device_index 0\n'
                   'cfg_jtag_flash_erase -device_index 0\n'
                   'cfg_jtag_flash_program -device_index 0\n'
                    'cfg_jtag_flash_verify -device_index 0\n') % tcl_word(bit)
    text += scan_guard(log)
    text += '''if {[string first "This device configure situation (done bit): 1" $motion_scan] < 0} {
    error "MOTION_GUARD: final target DONE is not asserted"
}
'''
    # All operations are inside one Tcl evaluation, so a guard error cannot
    # leave subsequent top-level commands available to a line-by-line runner.
    return 'if {[catch {\n' + text + '\n} motion_error]} {\nerror "MOTION_GUARD: $motion_error"\n}\n'


def parse_log(text, mode):
    text = text.replace('\r\n', '\n')
    errors = ERROR.findall(text)
    scan = re.search(r'Executing : cfg_scan_chain\r?\n(.*?)'
                     r'Executing : cfg_scan_chain successfully\.', text, re.S)
    devices = re.findall(r'^PG[A-Z0-9]+(?:-[A-Za-z0-9]+)?\s*$', scan[1], re.M) if scan else []
    stages = {'scan_success': bool(scan),
              'target_single': [d.strip() for d in devices] == [TARGET] and bool(scan)
                  and scan[1].count('This device configure situation (done bit):') == 1,
              'device_done': False, 'program_success': False}
    if mode == 'sram':
        section = text[text.find('Executing : cfg_program -device_index 0\n'):]
        stages['device_done'] = bool(re.search(r'The done bit is 1\b', section))
        stages['program_success'] = bool(re.search(
            r'COMMAND\[Program\] execute successfully', section)) and bool(re.search(
            r'Executing : cfg_program -device_index 0 successfully\.', section))
    else:
        for name in ('scan_device', 'assign_file', 'erase', 'program', 'verify'):
            stages['flash_' + name] = bool(re.search(
                r'Executing : cfg_jtag_flash_' + name + r' [^\n]*successfully\.', text))
        stages['program_success'] = stages['flash_program'] and stages['flash_verify']
    operation = ('Executing : cfg_program -device_index 0 successfully.' if mode == 'sram'
                 else 'Executing : cfg_jtag_flash_verify -device_index 0 successfully.')
    operation_end = text.rfind(operation)
    final = text[operation_end + len(operation):] if operation_end >= 0 else ''
    final_scan = re.search(r'Executing : cfg_scan_chain\n(.*?)'
                           r'Executing : cfg_scan_chain successfully\.', final, re.S)
    final_devices = re.findall(r'^PG[A-Z0-9]+(?:-[A-Za-z0-9]+)?\s*$',
                               final_scan[1], re.M) if final_scan else []
    stages['final_scan_success'] = bool(final_scan)
    stages['final_target_single'] = ([d.strip() for d in final_devices] == [TARGET]
                                     and bool(final_scan) and final_scan[1].count(
                                         'This device configure situation (done bit):') == 1)
    stages['device_done'] = (stages['final_target_single'] and
                             'This device configure situation (done bit): 1' in final_scan[1])
    return stages, errors


def idle():
    query = ("Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {$_.Name -match "
             "'^(pds|pds_shell|pnr|ta|bitgen|pne|ppc|ppp|synth|cdt_js|cdt_cfg|cdt_cfg_shell)\\.exe$'} "
             '| Select-Object ProcessId,Name | ConvertTo-Json -Compress')
    result = subprocess.run(['powershell', '-NoProfile', '-Command', query],
                            capture_output=True, text=True, timeout=20, check=True)
    require(not result.stdout.strip(), 'Vendor jobs active; no processes stopped: ' + result.stdout.strip())
    # Bind-only check; no connection or board scan.
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', PORT))


def close_windows(pid):
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

    @callback_type
    def close(hwnd, unused):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE, normal GUI shutdown
        return True
    user32.EnumWindows(close, 0)


def stop_owned(proc, normal_only=False):
    if proc is None or proc.poll() is not None:
        return
    close_windows(proc.pid)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        require(not normal_only, 'Programmer ignored WM_CLOSE; left owned PID %s open' % proc.pid)
        proc.terminate()  # only the Popen-owned PID, never a process name/tree
        proc.wait(timeout=5)


def run(args, receipt, directory, bit, digest):
    require(os.name == 'nt', 'Vendor execution requires Windows')
    require(all((BIN / name).is_file() for name in ('cdt_js.exe', 'cdt_cfg.exe')), 'Vendor tools missing')
    idle()
    # Copy protects against source being replaced while the programmer consumes it.
    frozen = directory / 'validated.sbit'
    shutil.copyfile(bit, frozen)
    require(sha(frozen) == digest and sha(bit) == digest, 'Bit changed before programming')
    logfile = directory / 'log/cfg.log'
    (directory / 'log').mkdir()
    tcl = directory / 'program.tcl'
    tcl.write_text(script(frozen, args.mode, logfile), encoding='utf-8')
    receipt['tcl'] = str(tcl)
    receipt['logs'] = [str(logfile), str(directory / 'server.log'), str(directory / 'client.log')]
    server = client = None
    with (directory / 'server.log').open('wb') as serverout, (directory / 'client.log').open('wb') as clientout:
        try:
            server = subprocess.Popen([str(BIN / 'cdt_js.exe'), '-port', str(PORT)],
                                      cwd=directory, stdin=subprocess.DEVNULL,
                                      stdout=serverout, stderr=subprocess.STDOUT)
            receipt['server_pid'] = server.pid
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                text = (directory / 'server.log').read_bytes().decode('gb18030', errors='replace')
                require(server.poll() is None, 'Owned JTAG server exited before ready')
                require(not ERROR.search(text), 'JTAG server startup error; inspect server.log')
                if 'To connect this JtagServer instance use port : 65426' in text:
                    break
                time.sleep(0.2)
            else:
                raise RuntimeError('JTAG server readiness not proven within 20s')
            client = subprocess.Popen([str(BIN / 'cdt_cfg.exe'), '-ip', '127.0.0.1',
                                       '-port', str(PORT), '-file', str(tcl)], cwd=directory,
                                      stdin=subprocess.DEVNULL, stdout=clientout, stderr=subprocess.STDOUT)
            receipt['client_pid'] = client.pid
            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline:
                text = logfile.read_bytes().decode('gb18030', errors='replace') if logfile.exists() else ''
                stages, errors = parse_log(text.replace('\r\n', '\n'), args.mode)
                receipt['stages'] = stages
                other = (directory / 'client.log').read_bytes().decode('gb18030', errors='replace')
                servertext = (directory / 'server.log').read_bytes().decode('gb18030', errors='replace')
                receipt['stage_errors'] = [line for line in (text + '\n' + other + '\n' + servertext).splitlines() if ERROR.search(line)]
                require(not errors and not receipt['stage_errors'], 'Programmer reported errors')
                if all(stages.values()):
                    stop_owned(client, normal_only=True)
                    require(client.returncode == 0, 'Programmer exit code after success: %s' % client.returncode)
                    final_text = logfile.read_bytes().decode('gb18030', errors='replace')
                    final_other = (directory / 'client.log').read_bytes().decode('gb18030', errors='replace')
                    final_server = (directory / 'server.log').read_bytes().decode('gb18030', errors='replace')
                    receipt['stages'], final_errors = parse_log(final_text, args.mode)
                    require(not final_errors and not ERROR.search(final_other + '\n' + final_server)
                            and all(receipt['stages'].values()),
                            'Final flushed programmer logs do not establish success')
                    receipt['status'] = 'success'
                    return
                require(client.poll() is None, 'Programmer exited without definitive success')
                time.sleep(0.25)
            raise RuntimeError('Programmer timeout without definitive success')
        finally:
            # An unresponsive programmer after success is left visible for inspection;
            # other failure/timeout cleanup is restricted to our own child processes.
            if client is not None and client.poll() is None:
                if receipt.get('stages') and all(receipt['stages'].values()):
                    receipt['cleanup_error'] = 'Owned programmer still open after WM_CLOSE'
                elif args.mode == 'flash':
                    receipt['cleanup_error'] = 'Flash operation unresolved; owned client and server left running for inspection'
                else:
                    stop_owned(client)
            if not (args.mode == 'flash' and client is not None and client.poll() is None):
                stop_owned(server)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--bit', required=True)
    parser.add_argument('--build-status', required=True)
    parser.add_argument('--manifest')
    parser.add_argument('--mode', choices=('sram', 'flash'), default='sram')
    parser.add_argument('--sram-receipt')
    parser.add_argument('--acceptance')
    parser.add_argument('--check', action='store_true', help='Validate/render only; no vendor/process/socket access')
    parser.add_argument('--timeout', type=int, default=300, help='Program stage seconds (1..1800)')
    parser.add_argument('--log-dir', help='Parent directory for unique retained run')
    args = parser.parse_args()
    require(1 <= args.timeout <= 1800, '--timeout must be 1..1800')
    parent = Path(args.log_dir).resolve() if args.log_dir else Path(__file__).resolve().parents[1] / 'motion_100h/program'
    directory = parent / ('run_' + time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8])
    directory.mkdir(parents=True)
    receipt = {'status': 'blocked', 'target': TARGET, 'mode': args.mode, 'bit': args.bit,
               'stages': {}, 'stage_errors': [], 'check_only': args.check,
               'rollback_command': [str(BIN / 'cdt_cfg.exe'), '-ip', '127.0.0.1', '-port', str(PORT),
                                    '-file', str(directory / 'rollback_sram.tcl')],
               'rollback_server_command': [str(BIN / 'cdt_js.exe'), '-port', str(PORT)],
               'rollback_note': 'SRAM baseline only; rerun idle/scan checks before manual rollback. Flash remains unchanged.'}
    try:
        bit, digest, proof = evidence(args)
        require(BASELINE.is_file() and sha(BASELINE) == BASELINE_SHA256,
                'Retained rollback bit does not match the verified running baseline')
        receipt.update(bit=str(bit), bit_sha256=digest, evidence=proof)
        rollback = directory / 'rollback_sram.tcl'
        rollback.write_text(script(BASELINE, 'sram', directory / 'log/cfg.log'), encoding='utf-8')
        receipt['rollback_baseline_sha256'] = sha(BASELINE) if BASELINE.is_file() else None
        if args.check:
            (directory / 'program.tcl').write_text(script(bit, args.mode, directory / 'log/cfg.log'), encoding='utf-8')
            receipt['status'] = 'validated_only'
        else:
            run(args, receipt, directory, bit, digest)
    except Exception as error:
        receipt['status'] = 'blocked'
        receipt['error'] = str(error)
    finally:
        receipt['retained_directory'] = str(directory)
        receipt['updated'] = time.strftime('%Y-%m-%d %H:%M:%S')
        (directory / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        print(json.dumps(receipt, indent=2), flush=True)
    return 0 if receipt['status'] in ('success', 'validated_only') else 1


if __name__ == '__main__':
    sys.exit(main())
