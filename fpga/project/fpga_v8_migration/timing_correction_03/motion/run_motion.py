"""Reuse TC01 oracle/checker generators, with isolated TC03 bindings and receipts.

Run from any directory: python .../motion/run_motion.py
No original runner is imported (its top-level code would overwrite old receipts).
"""
from pathlib import Path
import datetime
import difflib
import hashlib
import json
import re
import subprocess

HERE = Path(__file__).resolve().parent
TC03 = HERE.parent
MIGRATION = TC03.parent
PROJECT = MIGRATION.parent
TC01 = MIGRATION / 'timing_correction_01'
V4 = MIGRATION / 'whole_candidate_v4_route_01'
CANDIDATE = TC03 / 'rtl/block_motion_detector_tc03.v'
OUT = HERE / ('run_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
OUT.mkdir(parents=True)
SIM = Path(r'C:\modeltech64_10.6e\win64')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

protected = set((PROJECT / 'source').rglob('*'))
protected |= set((V4 / 'rtl').glob('*'))
protected |= set((TC01 / 'rtl').glob('*'))
protected |= {PROJECT / 'project.pds', TC01 / 'run_regression.py',
              TC01 / 'run_four_integration.py', TC01 / 'regression_result.json',
              TC01 / 'four_regression_result.json',
              PROJECT / 'sim/motion/tb_block_motion_detector.sv',
              PROJECT / 'sim/motion/tb_four_motion.sv'}
protected |= set(TC03.glob('*camera*.*'))
protected |= {TC03 / 'rtl/ov5640_cdc_tc03.v'}
protected = sorted(p for p in protected if p.is_file())
before = {str(p): sha(p) for p in protected}
(OUT / 'protected_before.json').write_text(json.dumps(before, indent=2) + '\n')
candidate_sha = sha(CANDIDATE)
paths = json.loads((V4 / 'evidence/all_reported_failing_paths.json').read_text())
motion_paths = [p for p in paths if 'mark_q[134]' in p.get('Startpoint', '')]
assert len(motion_paths) == 4 and all(p['Slack'] == -0.26 for p in motion_paths)
(OUT / 'motion_failing_paths.json').write_text(json.dumps(motion_paths, indent=2) + '\n')
baseline = V4 / 'rtl/block_motion_detector_tc01.v'
assert baseline.read_bytes() == (TC01 / 'rtl/block_motion_detector_tc01.v').read_bytes()
(OUT / 'motion_candidate.diff').write_text(''.join(difflib.unified_diff(
    baseline.read_text().splitlines(True), CANDIDATE.read_text().splitlines(True),
    fromfile=str(baseline), tofile=str(CANDIDATE))), encoding='ascii')

def run(exe, args, log, cwd):
    proc = subprocess.run([str(SIM / exe), *args], cwd=cwd,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (cwd / log).write_bytes(proc.stdout)
    text = proc.stdout.decode(errors='replace')
    if proc.returncode or re.search(r'\*\* (?:Error|Fatal):', text):
        raise RuntimeError(f'{exe}: {log}\n{text[-6000:]}')
    return text

# Reuse the motion-only prefix verbatim except paths/module name. Do not execute
# the decoder section or TC01's compile/run/receipt section.
generator = (TC01 / 'run_regression.py').read_text()
prefix = generator.split('# Discover every actual decoder port', 1)[0]
assert prefix.count("HERE = Path(__file__).resolve().parent") == 1
assert prefix.count("OUT = HERE / 'simulation'") == 1
prefix = prefix.replace('HERE = Path(__file__).resolve().parent', 'HERE = TC03')
prefix = prefix.replace("OUT = HERE / 'simulation'", 'OUT = PAIR')
prefix = prefix.replace('block_motion_detector_tc01', 'block_motion_detector_tc03')
PAIR = OUT / 'paired'
PAIR.mkdir()
ns = {'__file__': str(TC01 / 'run_regression.py'), 'TC03': TC03, 'PAIR': PAIR}
exec(compile(prefix, str(TC01 / 'run_regression.py') + ':motion-prefix', 'exec'), ns)
tb = ns['tb']
# Add a second 11-output cycle comparator against the exact V4 RTL, while the
# existing comparator retains the independent pre-TC01 original reference.
v4_paired = ns['paired'].replace('ref_', 'v4_').replace('paired_cycles', 'v4_cycles')
v4_paired = v4_paired.replace('block_motion_detector #(', 'block_motion_detector_tc01 #(')
v4_paired = v4_paired.replace(' original (', ' v4_original (')
v4_paired = v4_paired.replace('TC01 original cycle mismatch', 'TC03 V4 cycle mismatch')
tb = tb.replace('    reg [15:0] image', v4_paired + '\n    reg [15:0] image', 1)
tb = tb.replace('        done=1;', '        #2; $display("PASS paired11 W=%0d H=%0d STEP=%0d original_cycles=%0d V4_cycles=%0d",W,H,STEP,paired_cycles,v4_cycles);\n        done=1;')
tb_path = PAIR / 'tb_motion_actual_paired.sv'
tb_path.write_text(tb, encoding='ascii')
run('vlib.exe', ['work'], 'vlib.log', PAIR)
run('vlog.exe', ['-sv', '-work', 'work', str(ns['source_motion']), str(baseline),
                 str(CANDIDATE), str(tb_path)], 'compile.log', PAIR)
paired_log = run('vsim.exe', ['-c', '-voptargs=+acc', 'work.tb_block_motion_detector',
    '-do', 'onerror {quit -code 1}; onbreak {quit -code 1}; run -all; quit -code 0'],
    'motion.log', PAIR)
assert 'PASS ALL block_motion_detector self-checks' in paired_log
paired_counts = re.findall(r'PASS paired11 W=(\d+) H=(\d+) STEP=(\d+) original_cycles=(\d+) V4_cycles=(\d+)', paired_log)
assert len(paired_counts) == 5, paired_counts

# Reuse the actual four-stream integration driver with explicit redirected paths.
# This is a copy executed in memory; the old runner and receipts stay untouched.
four = (TC01 / 'run_four_integration.py').read_text()
four = four.replace('HERE=Path(__file__).resolve().parent', 'HERE=TC03')
four = four.replace("OUT=HERE/'four_simulation'", "OUT=RUN_OUT/'four'")
four = four.replace('block_motion_detector_tc01', 'block_motion_detector_tc03')
four = four.replace("HERE/'four_regression_result.json'", "RUN_OUT/'four_regression_result.json'")
exec(compile(four, str(TC01 / 'run_four_integration.py') + ':isolated-tc03', 'exec'),
     {'__file__': str(TC01 / 'run_four_integration.py'), 'TC03': TC03, 'RUN_OUT': OUT})
after = {str(p): sha(p) for p in protected}
assert before == after, 'Protected file changed'
assert sha(CANDIDATE) == candidate_sha, 'Candidate changed during regression'
result = {
    'status': 'PASS', 'candidate': str(CANDIDATE), 'candidate_sha256': candidate_sha,
    'v4_baseline_sha256': sha(baseline),
    'motion': 'TC01 five-geometry frame/history/literal oracle; all 11 public outputs compared every active cycle against original and exact V4',
    'paired_counts': [dict(zip(('width', 'height', 'step', 'original_cycles', 'v4_cycles'), map(int, row))) for row in paired_counts],
    'four_stream_integration': 'PASS actual full-resolution four-stream atomic register-record oracle',
    'reused_runners': {str(p): sha(p) for p in (TC01 / 'run_regression.py', TC01 / 'run_four_integration.py')},
    'protected_file_count': len(before), 'protected_hashes_unchanged': True,
    'artifacts': {str(p.relative_to(OUT)): sha(p) for p in OUT.rglob('*') if p.is_file() and p.suffix in ('.sv', '.v', '.log', '.diff', '.json')},
    'pds_invoked': False,
    'limitations': 'RTL simulation and structural optimization only; no candidate synthesis, placement/routing, STA, resource or physical timing improvement measured.'}
(OUT / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
