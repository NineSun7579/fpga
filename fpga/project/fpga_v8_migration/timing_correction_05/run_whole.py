"""Main-assistant-only fresh V7 build; sole new correction is TC03 -> TC05 detector."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
M = HERE.parent
BASE = M / 'whole_candidate_v6_route_01'
WORK = M / 'whole_candidate_v7_route_01'
PDS = Path(r'C:\pango\PDS_2022.2-SP6.4\bin\pds_shell.exe')
MODULES = {'block_motion_detector_tc03': ('block_motion_detector_tc05', 'rtl/block_motion_detector_tc03.v')}
TC04_MODULES = {'ov5640_cdc_tc04', 'fpga_v8_capture_lease_tc04', 'motion_stream_adapter_tc04',
                'fpga_v8_capture_ov5640_ddr_tc04', 'ov5640_ddr_tc04', 'axi_dma_write_tc04'}
REQUIRED = TC04_MODULES | {'block_motion_detector_tc05', 'fpga_v8_ddr_adapter_tc03',
                         'fpga_v8_pcie_fifo_h2f_tc02', 'fpga_v8_reset_fault_guard_02'}
FORBIDDEN = {'block_motion_detector', 'block_motion_detector_tc01', 'block_motion_detector_tc03',
             'ov5640_cdc', 'ov5640_cdc_tc03', 'fpga_v8_capture_lease', 'motion_stream_adapter',
             'fpga_v8_capture_ov5640_ddr', 'ov5640_ddr', 'axi_dma_write', 'axi_dma_write_tc02',
             'fpga_v8_ddr_adapter', 'fpga_v8_reset_fault_guard', 'fpga_v8_pcie_fifo_h2f_rfg01'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (WORK / name).write_text(json.dumps(value, indent=2), encoding='utf-8')


def inventory():
    return {str(p.relative_to(WORK)): sha(p) for folder in ['inputs', 'rtl']
            for p in (WORK / folder).rglob('*') if p.is_file()}


def baseline_inventory():
    files = [p for folder in ['inputs', 'rtl', 'evidence'] for p in (BASE / folder).rglob('*') if p.is_file()]
    files += [BASE / 'project.pds', BASE / 'place_route/fpga_v8_cooperative_top_v2_rfg01_pnr.adf']
    return {str(p): sha(p) for p in files}


def idle(label):
    command = ['powershell.exe', '-NoProfile', '-Command',
               'ConvertTo-Json -InputObject @(Get-Process pds,pds_shell -ErrorAction SilentlyContinue | Select-Object Id,ProcessName) -Compress']
    items = json.loads(subprocess.run(command, capture_output=True, check=True).stdout)
    save('processes_' + label + '.json', items)
    assert not items, 'PDS single-instance gate'


def replace_instances(data, old, new):
    return re.subn(rb'\b' + old + rb'(?=\s*(?:#\s*\(|\w+\s*\())', new, data)


def plan_binding():
    """Pure deterministic byte plan, shared with independent exhaustive audit."""
    project = (BASE / 'project.pds').read_bytes()
    oldpath = b'rtl/block_motion_detector_tc03.v'
    assert project.count(oldpath) == 1
    project = project.replace(oldpath, b'rtl/block_motion_detector_tc05.v')
    bindings, overrides, contents = {}, {}, {}
    registered = re.findall(rb'\(_file "([^"]+\.v)"', project)
    for token in registered:
        relative = token.decode('ascii')
        if relative == 'rtl/block_motion_detector_tc05.v':
            continue
        original = (BASE / relative).read_bytes()
        data, count = replace_instances(original, b'block_motion_detector_tc03', b'block_motion_detector_tc05')
        if not count:
            continue
        target = 'rtl/parent_tc05_' + hashlib.sha256(token).hexdigest()[:12] + '.v'
        assert not (BASE / target).exists() and project.count(token) == 1
        project = project.replace(token, target.encode())
        overrides[relative] = target
        contents[target] = data
        bindings[relative] = {'target': target, 'counts': {'block_motion_detector_tc03': count},
                              'before_sha256': hashlib.sha256(original).hexdigest(),
                              'after_sha256': hashlib.sha256(data).hexdigest()}
    assert bindings, 'No detector parent binding'
    project = re.sub(rb'\(_gci_state \(_integer \d+\)\)', b'(_gci_state (_integer 0))', project)
    return project, bindings, overrides, contents


def main():
    from accept_regressions import verify_regressions
    reviewed = verify_regressions()
    failures = json.loads((BASE / 'evidence/all_reported_failing_paths.json').read_bytes())
    assert len(failures) == 1 and failures[0]['Slack'] == -0.037 and '/WEA[0]' in failures[0]['Endpoint']
    baseline = baseline_inventory()
    project, bindings, overrides, contents = plan_binding()
    assert not WORK.exists(), 'Never overwrite a build attempt or V6 failure evidence'
    WORK.mkdir()
    idle('before_prepare')
    for folder in ['inputs', 'rtl']:
        shutil.copytree(BASE / folder, WORK / folder)
    shutil.copyfile(HERE / 'rtl/block_motion_detector_tc05.v', WORK / 'rtl/block_motion_detector_tc05.v')
    for target, data in contents.items():
        (WORK / target).write_bytes(data)
    (WORK / 'project.pds').write_bytes(project)
    reviewed = verify_regressions(WORK)
    save('tc05_regression_acceptance.json', reviewed)
    frozen = {str(p.relative_to(BASE)): sha(p) for p in (BASE / 'inputs').rglob('*') if p.is_file()}
    assert len(frozen) == 694 and all(sha(WORK / p) == h for p, h in frozen.items())
    save('binding_audit.json', {'exact_instance_replacements_only': True,
         'candidate_sources_match_tested_hashes': True, 'unchanged_input_files': len(frozen),
         'parent_bindings': bindings, 'input_overrides': overrides,
         'unchanged_constraints': {p: h for p, h in frozen.items() if p.endswith('.fdc')},
         'candidate_hashes': {'block_motion_detector_tc05': reviewed['candidate_sha256']},
         'tc04_candidate_hashes': reviewed['tc04_candidate_sha256'], 'programming_performed': False})
    save('baseline_before.json', baseline)
    (WORK / 'v6_failing_paths.json').write_bytes((BASE / 'evidence/all_reported_failing_paths.json').read_bytes())
    from audit_binding import main as audit_binding
    audit_binding()
    before = inventory()
    save('inputs_before.json', before)
    stages = []
    for stage in ['compile', 'synthesize', 'pnr']:
        idle('before_' + stage)
        print('Starting V7', stage, flush=True)
        with (WORK / (stage + '_shell.log')).open('xb') as log:
            result = subprocess.run([str(PDS), '-project', str(WORK / 'project.pds'),
                                     '-run', stage, '-work_dir', str(WORK)], cwd=WORK,
                                    stdout=log, stderr=subprocess.STDOUT)
        stages.append({'stage': stage, 'exit_code': result.returncode})
        save('flow_result.json', {'stages': stages, 'timing_verified': False})
        assert result.returncode == 0 and before == inventory(), stage
        assert baseline == baseline_inventory(), 'Frozen V6 drift'
        if stage == 'compile':
            log = WORK / 'compile/run.log'
            actual = {x.decode('ascii') for x in re.findall(rb'Elaborating module (\w+)', log.read_bytes())}
            assert REQUIRED <= actual and not FORBIDDEN & actual
            save('actual_elaboration.json', {'passed': True, 'required': sorted(REQUIRED),
                 'elaborated': sorted(actual), 'compile_log_sha256': sha(log)})
        if stage == 'synthesize':
            root = ET.parse(WORK / 'synthesize/snr.db').getroot()
            table = next(t for t in root.iter('table') if t.get('id') == 'synthesize_check_timing_summary')
            checks = {r.findall('data')[0].text: r.findall('data')[1].text for r in table.findall('row')}
            save('structural_gate.json', checks)
            assert all(checks[k] == '0' for k in ['loops', 'latchs', 'latch_loops', 'no_clock', 'unexpandable_clocks'])
    assert baseline == baseline_inventory()
    save('inputs_after.json', inventory())
    save('baseline_guard.json', {'files': len(baseline), 'unchanged': True, 'v6_failure_preserved': True})
    print('V7 routed; final STA and physical audit still required', flush=True)


if __name__ == '__main__':
    main()
