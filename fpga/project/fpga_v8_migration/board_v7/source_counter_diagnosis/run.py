from pathlib import Path
import hashlib, subprocess
here=Path(__file__).resolve().parent
root=here.parent.parent/'whole_candidate_v7_route_01'
sources=[root/'rtl/ov5640_cdc_tc04.v',root/'inputs/source/ov5640/ov5640/cmos_capture.v']
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
bin=Path('C:/modeltech64_10.6e/win64')
def run(exe,args,log):
 r=subprocess.run([str(bin/exe),*args],cwd=here,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 (here/log).write_bytes(r.stdout)
 print(r.stdout.decode(errors='replace'))
 if r.returncode: raise SystemExit(r.returncode)
run('vlib.exe',['work'],'vlib.log')
run('vlog.exe',['-sv',*[str(p) for p in sources],'tb_source.sv','tb_snapshot.sv'],'compile.log')
run('vsim.exe',['-c','-voptargs=+acc','tb_source','-do','onerror {quit -code 1}; run -all; quit -code 0'],'simulation.log')
assert b'ALL_PASS' in (here/'simulation.log').read_bytes()
run('vsim.exe',['-c','-voptargs=+acc','tb_snapshot','-do','run -all; quit -code 0'],'snapshot.log')
assert b'SNAPSHOT_ALL_PASS' in (here/'snapshot.log').read_bytes()
assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
(here/'source_hashes.txt').write_text('\n'.join(f'{v}  {k}' for k,v in before.items())+'\n',encoding='ascii')
