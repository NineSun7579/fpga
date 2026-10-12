from pathlib import Path
import subprocess, json, hashlib
HERE=Path(__file__).resolve().parent
OUT=HERE/'artifacts'
SIM=Path(r'C:\modeltech64_10.6e\win64')
def run(args,label):
    p=subprocess.run([str(x) for x in args],cwd=OUT,capture_output=True,timeout=90)
    data=p.stdout+p.stderr
    (OUT/(label+'.log')).write_bytes(data)
    assert p.returncode==0 and b'** Error' not in data and b'** Fatal' not in data,data.decode(errors='replace')
    return data
OUT.mkdir(exist_ok=True)
run([SIM/'vlib.exe','work'],'vlib')
run([SIM/'vlog.exe','-sv',HERE/'fpga_v8_reset_fault_guard_02.v',HERE/'tb_guard_02.sv'],'compile')
for mode in range(9):
    data=run([SIM/'vsim.exe','-c','-onfinish','stop','work.tb_guard_02','+MODE='+str(mode),'-do','run -all; quit -f'],'case_'+str(mode))
    assert b'GUARD02_PASS' in data
    print('PASS',mode,flush=True)
(OUT/'results.json').write_text(json.dumps({'passed_cases':9,'source_sha256':hashlib.sha256((HERE/'fpga_v8_reset_fault_guard_02.v').read_bytes()).hexdigest(),'pds_structure_verified':False,'routed_timing_verified':False},indent=2))
