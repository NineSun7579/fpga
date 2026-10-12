"""Negative control: the actual TC05 stress checker must reject a stuck qualifier."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import re
import subprocess

HERE = Path(__file__).resolve().parents[1]
SIM = Path(os.environ.get('MODELSIM_BIN', r'C:\modeltech64_10.6e\win64'))


def main():
    runs = sorted((HERE / 'receipts').glob('detector_*/compile_sources.json'))
    assert runs, 'Run run_detector.py first to generate the actual stress checker'
    generated = runs[-1].parent
    inputs = json.loads(runs[-1].read_bytes())
    sources = [Path(p) for p in inputs if Path(p).name in (
        'block_motion_detector.v', 'block_motion_detector_tc01.v',
        'block_motion_detector_tc03.v', 'block_motion_detector_tc05.v', 'tb_stress.sv')]
    assert len(sources) == 5
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    out = HERE / 'receipts' / ('monitor_fault_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    out.mkdir()

    def run(exe, args, label, expected_fault=False):
        proc = subprocess.run([str(SIM / exe), *map(str, args)], cwd=out,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        (out / (label + '.log')).write_bytes(proc.stdout)
        text = proc.stdout.decode(errors='replace')
        if expected_fault:
            # This ModelSim configuration exits zero for HDL $fatal; require
            # the exact fatal diagnosis and time, rather than its exit code.
            assert '** Fatal: TC05 lookahead invariant' in text and 'Time: 47 ns' in text, text
        else:
            assert proc.returncode == 0 and not re.search(r'\*\* (?:Error|Fatal):', text), text

    run('vlib.exe', ['work'], 'vlib')
    run('vlog.exe', ['-sv', *sources], 'compile')
    run('vsim.exe', ['-c', '-vopt', '-voptargs=+acc', 'work.tb_stress', '-do',
        'onerror {quit -code 1}; onbreak {quit -code 1}; '
        'force -freeze sim:/tb_stress/a/dut/history_eligible 0 46ns; run -all; quit -code 0'],
        'fault', expected_fault=True)
    assert before == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    result = {'status': 'PASS', 'negative_control': 'Forced history_eligible=0 at 46ns; actual RTL stress monitor rejected with TC05 lookahead invariant',
              'generated_checker': str(generated / 'tb_stress.sv'), 'inputs': before,
              'pds_invoked': False}
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'receipts': str(out)}, indent=2))


if __name__ == '__main__':
    main()
