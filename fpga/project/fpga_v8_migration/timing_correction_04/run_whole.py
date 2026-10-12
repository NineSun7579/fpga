"""Fresh V6 build from frozen V5, gated by reviewed TC04 regressions."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
M = HERE.parent
BASE = M / 'whole_candidate_v5_route_01'
WORK = M / 'whole_candidate_v6_route_01'
PDS = Path(r'C:\pango\PDS_2022.2-SP6.4\bin\pds_shell.exe')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (WORK / name).write_text(json.dumps(value, indent=2), encoding='utf-8')


def inventory():
    return {str(p.relative_to(WORK)): sha(p) for folder in ['inputs', 'rtl']
            for p in (WORK / folder).rglob('*') if p.is_file()}


def idle(label):
    command = ['powershell.exe', '-NoProfile', '-Command',
               'ConvertTo-Json -InputObject @(Get-Process pds,pds_shell -ErrorAction SilentlyContinue | Select-Object Id,ProcessName) -Compress']
    items = json.loads(subprocess.run(command, capture_output=True, check=True).stdout)
    save('processes_' + label + '.json', items)
    assert not items, 'PDS single-instance gate'


def replace_instances(data, old, new):
    return re.subn(rb'\b' + old + rb'(?=\s*(?:#\s*\(|\w+\s*\())', new, data)


MODULES = {
    'ov5640_cdc_tc03': ('ov5640_cdc_tc04', 'rtl/ov5640_cdc_tc03.v'),
    'fpga_v8_capture_lease': ('fpga_v8_capture_lease_tc04', 'rtl/fpga_v8_capture_lease.v'),
    'motion_stream_adapter': ('motion_stream_adapter_tc04', 'rtl/motion_stream_adapter.v'),
    'fpga_v8_capture_ov5640_ddr': ('fpga_v8_capture_ov5640_ddr_tc04', 'rtl/fpga_v8_capture_ov5640_ddr.v'),
    'ov5640_ddr': ('ov5640_ddr_tc04', 'inputs/source/ov5640/ov5640_ddr/ov5640_ddr.v'),
    'axi_dma_write_tc02': ('axi_dma_write_tc04', 'rtl/axi_dma_write_tc02.v'),
}


def main():
    reviewed = json.loads((HERE / 'regression_acceptance.json').read_bytes())
    assert reviewed['passed'] and set(reviewed['modules']) == {new for new, oldpath in MODULES.values()}
    assert all(sha(Path(p)) == h for p, h in reviewed['file_sha256'].items())
    assert all(sha(HERE / 'rtl' / (new + '.v')) == reviewed['candidate_sha256'][new]
               for new, oldpath in MODULES.values())
    assert not WORK.exists(), 'Do not overwrite implementation attempts'
    WORK.mkdir()
    idle('before_prepare')
    baseline = {str(p): sha(p) for folder in ['inputs', 'rtl']
                for p in (BASE / folder).rglob('*') if p.is_file()}
    for folder in ['inputs', 'rtl']:
        shutil.copytree(BASE / folder, WORK / folder)
    project = (BASE / 'project.pds').read_bytes()
    overrides = {}
    bindings = {}
    for old, (new, oldpath) in MODULES.items():
        newpath = 'rtl/' + new + '.v'
        shutil.copyfile(HERE / newpath, WORK / newpath)
        assert project.count(oldpath.encode()) == 1, oldpath
        project = project.replace(oldpath.encode(), newpath.encode())
    # Process all registered parents. Input files are overridden, never edited.
    registered = re.findall(rb'\(_file "([^"]+\.v)"', project)
    candidate_paths = {'rtl/' + new + '.v' for new, oldpath in MODULES.values()}
    for token in registered:
        relative = token.decode('ascii')
        if relative in candidate_paths:
            continue
        path = WORK / relative
        data = path.read_bytes()
        original = data
        counts = {}
        for old, (new, oldpath) in MODULES.items():
            data, count = replace_instances(data, old.encode(), new.encode())
            if count:
                counts[old] = count
        if data == original:
            continue
        if relative.startswith('inputs/'):
            target = 'rtl/parent_tc04_' + hashlib.sha256(token).hexdigest()[:12] + '.v'
            assert project.count(token) == 1
            project = project.replace(token, target.encode())
            overrides[relative] = target
        else:
            target = relative
        (WORK / target).write_bytes(data)
        bindings[relative] = {'target': target, 'counts': counts,
                              'before_sha256': hashlib.sha256(original).hexdigest(),
                              'after_sha256': sha(WORK / target)}
    assert all(any(old in entry['counts'] for entry in bindings.values()) for old in MODULES), 'Unbound candidate'
    project = re.sub(rb'\(_gci_state \(_integer \d+\)\)', b'(_gci_state (_integer 0))', project)
    (WORK / 'project.pds').write_bytes(project)
    frozen = {str(p.relative_to(BASE)): sha(p) for p in (BASE / 'inputs').rglob('*') if p.is_file()}
    assert len(frozen) == 694 and all(sha(WORK / p) == h for p, h in frozen.items())
    save('binding_audit.json', {'exact_instance_replacements_only': True,
         'candidate_sources_match_tested_hashes': True, 'unchanged_input_files': len(frozen),
         'parent_bindings': bindings, 'input_overrides': overrides,
         'unchanged_constraints': {p: h for p, h in frozen.items() if p.endswith('.fdc')},
         'candidate_hashes': reviewed['candidate_sha256'], 'programming_performed': False})
    before = inventory()
    save('inputs_before.json', before)
    stages = []
    for stage in ['compile', 'synthesize', 'pnr']:
        idle('before_' + stage)
        print('Starting', stage, flush=True)
        with (WORK / (stage + '_shell.log')).open('xb') as log:
            result = subprocess.run([str(PDS), '-project', str(WORK / 'project.pds'),
                                     '-run', stage, '-work_dir', str(WORK)], cwd=WORK,
                                    stdout=log, stderr=subprocess.STDOUT)
        stages.append({'stage': stage, 'exit_code': result.returncode})
        save('flow_result.json', {'stages': stages, 'timing_verified': False})
        assert result.returncode == 0, stage
        assert before == inventory(), 'Local input drift'
        if stage == 'compile':
            log = WORK / 'compile/run.log'
            elaborated = set(x.decode() for x in re.findall(rb'Elaborating module (\w+)', log.read_bytes()))
            required = {new for new, oldpath in MODULES.values()} | {
                'block_motion_detector_tc03', 'fpga_v8_ddr_adapter_tc03',
                'fpga_v8_pcie_fifo_h2f_tc02', 'fpga_v8_reset_fault_guard_02'}
            assert required <= elaborated, required - elaborated
            assert not set(MODULES) & elaborated, set(MODULES) & elaborated
            save('actual_elaboration.json', {'passed': True, 'required': sorted(required),
                 'elaborated': sorted(elaborated), 'compile_log_sha256': sha(log)})
        if stage == 'synthesize':
            root = ET.parse(WORK / 'synthesize/snr.db').getroot()
            table = next(t for t in root.iter('table') if t.get('id') == 'synthesize_check_timing_summary')
            checks = {r.findall('data')[0].text: r.findall('data')[1].text for r in table.findall('row')}
            save('structural_gate.json', checks)
            assert all(checks[k] == '0' for k in ['loops', 'latchs', 'latch_loops', 'no_clock', 'unexpandable_clocks'])
            print('Whole structural gate PASS', flush=True)
    assert all(sha(Path(p)) == h for p, h in baseline.items()), 'Frozen baseline drift'
    save('inputs_after.json', inventory())
    save('baseline_guard.json', {'files': len(baseline), 'unchanged': True})
    print('Route finished; final slow/fast STA audit required', flush=True)


if __name__ == '__main__':
    main()
