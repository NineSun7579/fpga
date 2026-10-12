"""Open copies and export constraints only; preserve all original artifacts."""
from pathlib import Path
import ctypes
import hashlib
import json
import shutil
import subprocess
import time
import traceback

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'source_diagnostics_timing_build_01/route_attempt_03'
PDS = Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def main():
    assert not (HERE / 'copied').exists(), 'Preserve every attempt'
    cmd = 'ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process | Select-Object ProcessId,Name,CommandLine) -Compress'
    processes = json.loads(subprocess.check_output(['powershell', '-NoProfile', '-Command', cmd]))
    assert not [p for p in processes if p['Name'].lower() in {'pds.exe', 'pds_shell.exe', 'ta.exe'}], 'PDS/GUI busy'
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.ReleaseMutex.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.CreateMutexW(None, True, 'Global\\ov56401_PDS_single_instance')
    if not handle or ctypes.get_last_error() == 183:
        if handle:
            kernel.CloseHandle(handle)
        raise RuntimeError('Existing cooperating PDS controller')
    try:
        files = [SOURCE / 'project.pds']
        for directory in ['compile', 'synthesize', 'device_map', 'place_route']:
            files += [p for p in (SOURCE / directory).iterdir() if p.is_file() and p.suffix.lower() in {'.adf', '.db', '.pcf'}]
        files += list((SOURCE / 'constraints_candidate').glob('*.fdc'))
        required = ['compile/v7_sdt_top_comp.adf', 'compile/cmr.db',
                    'synthesize/v7_sdt_top_syn.adf', 'synthesize/snr.db',
                    'device_map/v7_sdt_top_map.adf', 'device_map/dmr.db',
                    'place_route/v7_sdt_top_pnr.adf', 'place_route/prr.db']
        assert all(SOURCE / r in files for r in required), 'Required real stage database missing'
        bindings = []
        for original in files:
            target = HERE / 'copied' / original.relative_to(SOURCE)
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = sha(original)
            shutil.copy2(original, target)
            assert sha(target) == digest, 'Copied input mismatch'
            bindings.append({'source': str(original), 'copy': str(target), 'sha256': digest})
        (HERE / 'copy_bindings.json').write_text(json.dumps(bindings, indent=2), encoding='ascii')
        script = HERE / 'context_probe.tcl'
        argv = [str(PDS), '-file', str(script), '-work_dir', str(HERE), '-project_name', 'io_bank_context04']
        started = time.time()
        with (HERE / 'context_probe.log').open('xb') as stream:
            result = subprocess.run(argv, cwd=HERE, stdout=stream, stderr=subprocess.STDOUT)
        raw = (HERE / 'context_probe.log').read_bytes()
        drift = [r['source'] for r in bindings if sha(Path(r['source'])) != r['sha256']]
        outputs = [{'path': str(p), 'sha256': sha(p), 'bytes': p.stat().st_size} for p in HERE.rglob('context_roundtrip.fdc')]
        record = {'scope': 'Copied project context and constraint export only; not IO bank acceptance',
                  'started_unix': started, 'finished_unix': time.time(), 'exit_code': result.returncode,
                  'script_sha256': sha(script), 'log_sha256': hashlib.sha256(raw).hexdigest(),
                  'source_drift': drift, 'copied_project_open_marker': b'IO_BANK_CONTEXT_PROJECT_OPENED' in raw,
                  'completion_marker': b'IO_BANK_CONTEXT_EXPORT_COMPLETE' in raw, 'outputs': outputs,
                  'build_or_program': False, 'IO_gate_passed': False}
        (HERE / 'context_receipt.json').write_text(json.dumps(record, indent=2), encoding='ascii')
        assert not drift, 'Original source/database drift'
        assert result.returncode == 0 and record['completion_marker'] and outputs, 'Context/export experiment failed'
        print(json.dumps(record, indent=2), flush=True)
    finally:
        kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)

if __name__ == '__main__':
    try:
        main()
    except BaseException:
        (HERE / 'context_failure.txt').write_text(traceback.format_exc(), encoding='utf8')
        raise
