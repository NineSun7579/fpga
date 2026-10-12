"""Wait for the existing delivery pipeline process event, then audit locally."""
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import sys
from run_whole import WORK


def main():
    pid = int(sys.argv[1])
    marker = WORK / 'acceptance_audit_attached.json'
    assert not marker.exists(), 'Acceptance auditor already attached'
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x100000, False, pid)
    if handle:
        command = ['powershell.exe', '-NoProfile', '-Command',
                   'Get-CimInstance Win32_Process -Filter "ProcessId=' + str(pid) +
                   '" | Select-Object Name,CommandLine | ConvertTo-Json -Compress']
        info = json.loads(subprocess.run(command, capture_output=True, check=True).stdout or 'null')
        if info is not None:
            assert info['Name'].lower() == 'python.exe' and 'finish_when_ready.py' in info['CommandLine']
        else:
            assert kernel.WaitForSingleObject(handle, 0) == 0
    else:
        assert (WORK / 'finish_pipeline_result.json').exists(), 'Pipeline unavailable'
    marker.write_text(json.dumps({'pipeline_pid': pid, 'wait_method': 'Windows process completion event',
                                  'programming_performed': False}, indent=2))
    if handle:
        print('Attached acceptance audit to pipeline completion event', pid, flush=True)
        try:
            assert kernel.WaitForSingleObject(handle, 0xffffffff) == 0
        finally:
            kernel.CloseHandle(handle)
    result = json.loads((WORK / 'finish_pipeline_result.json').read_bytes())
    assert [s['script'] for s in result['steps']] == ['export_whole.py', 'generate_bitstream.py', 'verify_delivery.py']
    assert all(s['exit_code'] == 0 for s in result['steps']), 'Delivery pipeline failed'
    audit = subprocess.run([sys.executable, str(Path(__file__).with_name('audit_acceptance.py'))])
    assert audit.returncode == 0, 'Independent acceptance audit failed'


if __name__ == '__main__':
    main()
