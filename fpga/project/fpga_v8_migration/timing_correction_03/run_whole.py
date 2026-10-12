"""Fresh V5 build. Preserve frozen inputs; bind tested isolated RTL copies."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
M = HERE.parent
BASE = M / 'whole_candidate_v4_route_01'
WORK = M / 'whole_candidate_v5_route_01'
PDS = Path(r'C:\pango\PDS_2022.2-SP6.4\bin\pds_shell.exe')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


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


def main():
    # Caller must first finish and review all three isolated regression receipts.
    camera = json.loads((HERE / 'camera_artifacts/results.json').read_bytes())
    adapter = json.loads((HERE / 'adapter_artifacts/adapter_results.json').read_bytes())
    assert camera['passed'] and len(camera['runs']) == 12
    assert all(sha(Path(p)) == h for p, h in camera['file_sha256'].items())
    assert adapter['status'] == 'PASS'
    assert all(sha(M.parent / p) == h for p, h in adapter['source_sha256'].items())
    assert all(sha(HERE / 'adapter_artifacts' / p) == h for p, h in adapter['artifact_sha256'].items())
    assert (HERE / 'motion_acceptance.json').exists(), 'Reviewed motion regression receipt required'
    motion = json.loads((HERE / 'motion_acceptance.json').read_bytes())
    assert motion['passed'] and motion['four_camera_integration_passed']
    assert all(sha(Path(p)) == h for p, h in motion['file_sha256'].items())
    assert not WORK.exists(), 'Do not overwrite implementation attempts'
    WORK.mkdir()
    idle('before_prepare')
    baseline = {str(p): sha(p) for folder in ['inputs', 'rtl']
                for p in (BASE / folder).rglob('*') if p.is_file()}
    for folder in ['inputs', 'rtl']:
        shutil.copytree(BASE / folder, WORK / folder)
    names = ['ov5640_cdc_tc03.v', 'fpga_v8_ddr_adapter_tc03.v', 'block_motion_detector_tc03.v']
    for name in names:
        shutil.copyfile(HERE / 'rtl' / name, WORK / 'rtl' / name)
    project = (BASE / 'project.pds').read_bytes()
    substitutions = {
        b'inputs/source/ov5640/ov5640/ov5640_cdc.v': b'rtl/ov5640_cdc_tc03.v',
        b'rtl/fpga_v8_ddr_adapter.v': b'rtl/fpga_v8_ddr_adapter_tc03.v',
        b'rtl/block_motion_detector_tc01.v': b'rtl/block_motion_detector_tc03.v',
    }
    counts = {}
    # Override camera parents in rtl; frozen input tree remains byte-identical.
    for relative in ['inputs/source/ov5640/ov5640/ov5640.v', 'inputs/source/HDMI/hdmi_loop.v']:
        source = WORK / relative
        data, count = replace_instances(source.read_bytes(), b'ov5640_cdc', b'ov5640_cdc_tc03')
        assert count > 0, relative
        override = 'rtl/' + source.stem + '_tc03_binding.v'
        (WORK / override).write_bytes(data)
        substitutions[relative.encode()] = override.encode()
        counts[relative] = count
    for relative, old, new in [
        ('rtl/fpga_v8_cooperative_top_v2_rfg01.v', b'fpga_v8_ddr_adapter', b'fpga_v8_ddr_adapter_tc03'),
        ('rtl/motion_stream_adapter.v', b'block_motion_detector_tc01', b'block_motion_detector_tc03'),
    ]:
        target = WORK / relative
        data, count = replace_instances(target.read_bytes(), old, new)
        assert count == 1, (relative, count)
        target.write_bytes(data)
        counts[relative] = count
    for old, new in substitutions.items():
        assert project.count(old) == 1, old
        project = project.replace(old, new)
    project = re.sub(rb'\(_gci_state \(_integer \d+\)\)', b'(_gci_state (_integer 0))', project)
    (WORK / 'project.pds').write_bytes(project)
    frozen_inputs = {str(p.relative_to(BASE)): sha(p) for p in (BASE / 'inputs').rglob('*') if p.is_file()}
    assert all(sha(WORK / p) == h for p, h in frozen_inputs.items())
    changed_rtl = {'rtl/fpga_v8_cooperative_top_v2_rfg01.v', 'rtl/motion_stream_adapter.v'}
    assert all(sha(WORK / p.relative_to(BASE)) == sha(p)
               for p in (BASE / 'rtl').rglob('*') if p.is_file()
               and str(p.relative_to(BASE)).replace('\\', '/') not in changed_rtl)
    save('binding_audit.json', {'exact_top_instance_replacements_only': True,
         'candidate_sources_match_tested_hashes': True, 'unchanged_input_files': len(frozen_inputs),
         'parent_module_instance_replacements': counts,
         'unchanged_constraints': {p: h for p, h in frozen_inputs.items() if p.endswith('.fdc')},
         'external_top_api_unchanged': True, 'six_camera_connections_unchanged': True,
         'motion_connections_unchanged': True,
         'scope': 'Byte-identical frozen inputs and inherited RTL except module instance names; isolated camera parent copies.'})
    before = inventory()
    save('inputs_before.json', before)
    save('preparation.json', {'base': str(BASE), 'binding_counts': counts,
         'project_substitutions': {k.decode(): v.decode() for k, v in substitutions.items()},
         'candidate_sha256': {name: sha(HERE / 'rtl' / name) for name in names},
         'constraints_unchanged': True, 'programming_performed': False})
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
            elaborated = set(x.decode() for x in re.findall(rb'Elaborating module (\w+)', (WORK / 'compile/run.log').read_bytes()))
            required = {'ov5640_cdc_tc03', 'fpga_v8_ddr_adapter_tc03', 'block_motion_detector_tc03',
                        'axi_dma_write_tc02', 'fpga_v8_pcie_fifo_h2f_tc02', 'fpga_v8_reset_fault_guard_02'}
            assert required <= elaborated, required - elaborated
            assert not {'ov5640_cdc', 'fpga_v8_ddr_adapter', 'block_motion_detector_tc01'} & elaborated
            save('actual_elaboration.json', {'passed': True, 'required': sorted(required),
                 'elaborated': sorted(elaborated), 'compile_log_sha256': sha(WORK / 'compile/run.log')})
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
