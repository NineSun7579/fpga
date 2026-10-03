"""Prepare a distinct snapshot; --run launches only while PDS is idle.

Run with the shell tool's background notification mode. Never poll this runner.
The experiment uses the old mapped netlist, and is not a release build.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

TEMP = Path(os.environ['LOCALAPPDATA']) / 'Temp'
SOURCE = TEMP / 'sta50k201932_isolated'
DEST = TEMP / 'sta50k_holdexperiment'
ORIGINAL = Path('C:/Users/NineSun/Desktop/ov56401/ov5640_sfp480p_test/ov5640_sfp480p_test')
PDS = Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
SCRIPT = Path(__file__).with_name('sta50k_holdexperiment.tcl')
MAP = Path('device_map/hdmi_ddr_ov5640_top_map.adf')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def inventory(root):
    return {p.relative_to(root).as_posix(): sha(p)
            for p in sorted(root.rglob('*')) if p.is_file()}


def busy():
    query = ("Get-Process | Where-Object { $_.ProcessName -match "
             "'^(pds|pds_shell|pnr|ta)$' } | "
             "Select-Object Id,ProcessName | ConvertTo-Json -Compress")
    return subprocess.check_output(['powershell', '-NoProfile', '-Command', query],
                                   text=True).strip()


def save(name, data):
    (DEST / name).write_text(json.dumps(data, indent=2), encoding='ascii')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--resume', action='store_true', help='Retry existing verified copy')
    parser.add_argument('--timeout-seconds', type=int, default=3000)
    args = parser.parse_args()
    if DEST.exists() and not args.resume:
        raise SystemExit('Refusing to overwrite existing experiment: ' + str(DEST))
    if not (SOURCE / MAP).is_file():
        raise SystemExit('Missing verified snapshot mapped ADF')
    # A busy tool means prepare only; check again immediately before launch.
    initial_busy = busy()
    before = inventory(ORIGINAL)
    source_before = inventory(SOURCE)
    if args.resume:
        source_before = json.loads((DEST / 'copy_manifest.json').read_text())
        for name, digest in source_before.items():
            if name.startswith(('source/', 'ipcore/', 'compile/', 'synthesize/', 'device_map/')) or name == 'build.pds':
                if not (DEST / name).is_file() or sha(DEST / name) != digest:
                    raise SystemExit('Protected retry input changed: ' + name)
    else:
        shutil.copytree(SOURCE, DEST)
        copied = inventory(DEST)
        if copied != source_before:
            raise SystemExit('Snapshot changed during copy or copy integrity failed')
    if not args.resume and sha(DEST / 'place_route/hdmi_ddr_ov5640_top_pnr.adf') != \
            'dbf4a114f335e3f046c2a03544f0763953f1c09ae8bf4b69be75429692d36b98':
        raise SystemExit('Snapshot is not the documented 201932 baseline')
    save('copy_manifest.json', source_before)
    save('original_before.json', before)
    # Only copied PNR/report outputs are removed. Preserve mapping and all inputs.
    if (DEST / 'place_route').exists():
        shutil.rmtree(DEST / 'place_route')
    if (DEST / 'report_timing').exists():
        shutil.rmtree(DEST / 'report_timing')
    shutil.copy2(SCRIPT, DEST / SCRIPT.name)
    report_script = SCRIPT.with_name('sta50k_holdexperiment_report.tcl')
    shutil.copy2(report_script, DEST / report_script.name)
    command = [str(PDS), '-file', str(DEST / SCRIPT.name),
               '-work_dir', str(DEST), '-project_name', 'hold_physical_only']
    state = {'command': command, 'mapped_sha256': sha(DEST / MAP),
             'old_map_physical_only': True, 'initial_busy': initial_busy,
             'timeout_seconds': args.timeout_seconds,
             'status': 'prepared', 'started': time.strftime('%Y-%m-%d %H:%M:%S')}
    save('experiment_status.json', state)
    if args.run:
        current_busy = busy()
        if initial_busy or current_busy:
            state.update(status='prepared_busy_no_launch', current_busy=current_busy)
        else:
            state['status'] = 'running'
            save('experiment_status.json', state)
            print('Launching isolated physical-only PNR: ' + str(DEST), flush=True)
            with (DEST / 'hold_stdout.log').open('wb') as log:
                process = subprocess.Popen(command, cwd=DEST, stdout=log,
                                           stderr=subprocess.STDOUT)
                state['pid'] = process.pid
                save('experiment_status.json', state)
                try:
                    state['returncode'] = process.wait(timeout=args.timeout_seconds)
                    state['status'] = 'finished' if process.returncode == 0 else 'failed'
                except subprocess.TimeoutExpired:
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                   check=False, capture_output=True)
                    process.wait(timeout=30)
                    state['status'] = 'timeout'
            if state['status'] == 'finished':
                routed = DEST / 'place_route/hdmi_ddr_ov5640_top_pnr.adf'
                if not routed.is_file():
                    state['status'] = 'failed_missing_routed_adf'
                elif busy():
                    state['status'] = 'pnr_finished_report_busy_no_launch'
                else:
                    report_command = [str(PDS), '-file', str(DEST / report_script.name),
                                      '-work_dir', str(DEST), '-project_name', 'hold_report_only']
                    with (DEST / 'hold_report_stdout.log').open('wb') as log:
                        report_process = subprocess.Popen(report_command, cwd=DEST, stdout=log,
                                                          stderr=subprocess.STDOUT)
                        try:
                            state['report_returncode'] = report_process.wait(timeout=300)
                            if report_process.returncode:
                                state['status'] = 'pnr_finished_report_failed'
                        except subprocess.TimeoutExpired:
                            subprocess.run(['taskkill', '/PID', str(report_process.pid), '/T', '/F'],
                                           check=False, capture_output=True)
                            report_process.wait(timeout=30)
                            state['status'] = 'pnr_finished_report_timeout'
    after = inventory(ORIGINAL)
    save('original_after.json', after)
    changes = [name for name in sorted(before.keys() | after.keys())
               if before.get(name) != after.get(name)]
    save('original_audit.json', {'changed_added_or_missing': changes,
                                'note': 'Concurrent parent edits may appear; this runner never writes original.'})
    protected = {name: digest for name, digest in source_before.items()
                 if name.startswith(('source/', 'ipcore/', 'compile/', 'synthesize/',
                                     'device_map/')) or name == 'build.pds'}
    save('isolated_input_audit.json', {
        'checked': len(protected),
        'changed_or_missing': [name for name, digest in protected.items()
                               if not (DEST / name).is_file() or sha(DEST / name) != digest]})
    state['ended'] = time.strftime('%Y-%m-%d %H:%M:%S')
    save('experiment_status.json', state)
    print(json.dumps(state, indent=2), flush=True)


if __name__ == '__main__':
    main()
