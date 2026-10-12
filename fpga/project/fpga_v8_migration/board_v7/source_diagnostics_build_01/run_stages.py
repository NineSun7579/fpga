"""Compile/synthesize only to inspect real cells. PNR requires CDC approval evidence."""
from prepare import HERE, PDS, idle, inventory, protected, save, sha
import json, subprocess, re, xml.etree.ElementTree as ET

def main():
    before = json.loads((HERE / 'inputs_before.json').read_bytes())
    guard = json.loads((HERE / 'protected_before.json').read_bytes())
    stages = []
    for stage in ['compile', 'synthesize']:
        assert inventory() == before and protected() == guard
        idle('before_' + stage)
        cmd = [str(PDS), '-project', str(HERE / 'project.pds'), '-run', stage, '-work_dir', str(HERE)]
        print('START', stage, cmd, flush=True)
        with (HERE / (stage + '_shell.log')).open('xb') as log:
            result = subprocess.run(cmd, cwd=HERE, stdout=log, stderr=subprocess.STDOUT)
        stages.append({'stage':stage, 'command':cmd, 'exit_code':result.returncode})
        save('flow_result.json', {'stages':stages, 'timing_verified':False, 'cdc_gate_pending':True})
        assert inventory() == before and protected() == guard, 'Hash drift'
        assert result.returncode == 0, stage
        if stage == 'compile':
            data = (HERE / 'compile/run.log').read_bytes()
            actual = {x.decode() for x in re.findall(rb'Elaborating module (\w+)', data)}
            required = {'v7_sdt_top','v7_sdt_camera','v7_sdt_binding','v7_sdt_bus','v7_sfd_candidate',
                        'block_motion_detector_tc05','ov5640_cdc_tc04','fpga_v8_capture_lease_tc04',
                        'axi_dma_write_tc04','fpga_v8_ddr_adapter_tc03','fpga_v8_reset_fault_guard_02'}
            assert required <= actual, required - actual
            assert not any('cdc_boundary' in x for x in actual)
            save('actual_elaboration.json', {'required':sorted(required), 'actual':sorted(actual), 'passed':True})
        else:
            root = ET.parse(HERE / 'synthesize/snr.db').getroot()
            table = next(t for t in root.iter('table') if t.get('id') == 'synthesize_check_timing_summary')
            checks = {r.findall('data')[0].text:r.findall('data')[1].text for r in table.findall('row')}
            save('structural_gate.json', checks)
            assert all(checks[k] == '0' for k in ['loops','latchs','latch_loops','no_clock','unexpandable_clocks'])
        print('DONE', stage, result.returncode, flush=True)
    save('baseline_guard.json', {'unchanged':True, 'files':len(guard)})
    print('SYNTHESIS COMPLETE; PNR blocked pending nonempty CDC targets and exception precedence proof', flush=True)

if __name__ == '__main__':
    main()
