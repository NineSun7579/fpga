"""Single-instance interface discovery only; no DB load, build or acceptance."""
from pathlib import Path
import ctypes
import hashlib
import json
import subprocess
import time
import traceback

HERE = Path(__file__).resolve().parent
PDS = Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')

def main():
    receipt = HERE / 'discovery_receipt.json'
    log = HERE / 'discovery.log'
    assert not receipt.exists() and not log.exists(), 'Preserve every attempt'
    command = 'ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process | Select-Object ProcessId,Name,CommandLine) -Compress'
    processes = json.loads(subprocess.check_output(['powershell', '-NoProfile', '-Command', command]))
    assert not [p for p in processes if p['Name'].lower() in {'pds.exe', 'pds_shell.exe', 'ta.exe'}], 'PDS/GUI is busy'
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.ReleaseMutex.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.CreateMutexW(None, True, 'Global\\ov56401_PDS_single_instance')
    if not handle or ctypes.get_last_error() == 183:
        if handle:
            kernel.CloseHandle(handle)
        raise RuntimeError('Another cooperating PDS controller owns mutex')
    try:
        script = HERE / 'discover_interfaces.tcl'
        digest = hashlib.sha256(script.read_bytes()).hexdigest()
        argv = [str(PDS), '-file', str(script), '-work_dir', str(HERE), '-project_name', 'io_bank_interface_discovery01']
        started = time.time()
        with log.open('xb') as stream:
            result = subprocess.run(argv, cwd=HERE, stdout=stream, stderr=subprocess.STDOUT)
        raw = log.read_bytes()
        record = {'scope': 'Command/help discovery only; not IO acceptance', 'started_unix': started,
                  'finished_unix': time.time(), 'command': argv, 'exit_code': result.returncode,
                  'script_sha256': digest, 'log_sha256': hashlib.sha256(raw).hexdigest(),
                  'completion_marker': b'IO_BANK_DIAGNOSTIC_DISCOVERY_COMPLETE' in raw,
                  'db_loaded': False, 'build_or_program': False, 'IO_gate_passed': False}
        receipt.write_text(json.dumps(record, indent=2), encoding='ascii')
        assert result.returncode == 0 and record['completion_marker'], 'Discovery failed; retain raw log'
        assert hashlib.sha256(script.read_bytes()).hexdigest() == digest, 'Script drift'
        print(json.dumps(record, indent=2), flush=True)
    finally:
        kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)

if __name__ == '__main__':
    try:
        main()
    except BaseException:
        (HERE / 'discovery_failure.txt').write_text(traceback.format_exc(), encoding='utf8')
        raise
