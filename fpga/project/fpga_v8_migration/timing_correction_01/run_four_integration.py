"""Actual four full-resolution capture streams and atomic motion-record oracle."""
from pathlib import Path
import hashlib, json, re, subprocess
HERE=Path(__file__).resolve().parent
PROJECT=HERE.parent.parent
FROZEN=HERE.parent/'whole_candidate_v2_route_01/inputs/source/motion'
SIM=Path(r'C:\modeltech64_10.6e\win64')
OUT=HERE/'four_simulation'
OUT.mkdir(exist_ok=True)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
protected=[FROZEN/'motion_stream_adapter.v',FROZEN/'motion_register_bank.v',PROJECT/'sim/motion/tb_four_motion.sv']
before={str(p):sha(p) for p in protected}
raw=protected[0].read_bytes()
assert raw.count(b'block_motion_detector #(')==1
(OUT/'motion_stream_adapter_tc_binding.v').write_bytes(raw.replace(b'block_motion_detector #(',b'block_motion_detector_tc01 #('))
def run(exe,args,log):
    p=subprocess.run([str(SIM/exe),*args],cwd=OUT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (OUT/log).write_bytes(p.stdout)
    t=p.stdout.decode(errors='replace')
    if p.returncode or re.search(r'\*\* (?:Error|Fatal):',t): raise RuntimeError(t[-6000:])
    return t
run('vlib.exe',['work'],'vlib.log')
run('vlog.exe',['-sv','-work','work',str(HERE/'rtl/block_motion_detector_tc01.v'),
    str(OUT/'motion_stream_adapter_tc_binding.v'),str(protected[1]),str(protected[2])],'compile.log')
t=run('vsim.exe',['-c','-voptargs=+acc','work.tb_four_motion','-do',
    'onerror {quit -code 1}; onbreak {quit -code 1}; run -all; quit -code 0'],'four_motion.log')
assert 'PASS' in t and 'four' in t.lower(), t[-5000:]
assert before=={str(p):sha(p) for p in protected}
(HERE/'four_regression_result.json').write_text(json.dumps({'status':'PASS',
    'source_hashes':before,'candidate_sha256':sha(HERE/'rtl/block_motion_detector_tc01.v'),
    'binding_artifact_sha256':sha(OUT/'motion_stream_adapter_tc_binding.v'),
    'log':str(OUT/'four_motion.log'),'pds_invoked':False},indent=2)+'\n')
print(t[-6000:])
