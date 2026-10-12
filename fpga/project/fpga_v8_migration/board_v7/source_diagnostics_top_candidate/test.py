import subprocess,sys,json,hashlib
from run import P,F,SIM,run
subprocess.run([sys.executable,str(P/'make_tb.py')],check=True)
compiled=json.loads((P/'compiled_hashes.json').read_text())
assert all(hashlib.sha256(__import__('pathlib').Path(f).read_bytes()).hexdigest()==h for f,h in compiled.items()), 'Source changed since full compile; run run.py first'
run('vlog.exe',['-sv',P/'tb_sdt.sv'],'tb_compile.log')
s=run('vsim.exe',['-c','-vopt','-voptargs=+acc','-L','vendor','work.tb_sdt','-do','onerror {quit -code 1}; run -all; quit -f'],'top_simulation.log')
assert 'SDT_ALL_PASS' in s and 'FAIL' not in s
S=P.parent/'source_frame_diagnostics_candidate'
run('vlog.exe',['-sv',S/'tb_v7_sfd_candidate.sv'],'source_tb_compile.log')
s=run('vsim.exe',['-c','-novopt','work.tb_v7_sfd_candidate','-do','onerror {quit -code 1}; run -all; quit -f'],'source_regression.log')
assert 'SFD_ALL_PASS' in s and 'FAIL' not in s
before=json.loads((P/'source_hashes.json').read_text())
assert all(hashlib.sha256(__import__('pathlib').Path(f).read_bytes()).hexdigest()==h for f,h in before.items())
print('PROTECTED_HASHES_UNCHANGED')
