"""Re-run both prior suites only inside this new candidate directory."""
from pathlib import Path
import subprocess,os,re
from run import P,F,SIM
B=P.parent/'source_diagnostics_bus_candidate';S=P.parent/'source_frame_diagnostics_candidate'
D=P/'unit_regression';D.mkdir(exist_ok=True)
for name in ['fixture.vh','tb.sv']:(D/name).write_bytes((B/name).read_bytes())
def tool(exe,args,log):
 r=subprocess.run([str(SIM/exe),*map(str,args)],cwd=D,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 t=r.stdout.decode(errors='replace');(D/log).write_text(t,encoding='utf-8')
 print(log,t[-1200:]);assert r.returncode==0
 assert not re.search(r'\*\* (?:Error|Fatal)',t)
 return t
if not (D/'work').exists():tool('vlib.exe',['work'],'vlib.log')
tool('vlog.exe',['-sv',F/'inputs/source/ov5640/axi_to_axi_lite.v',F/'rtl/ovreg_axil_decode_tc01.v',F/'inputs/source/ov5640/ov5640/cmos_capture.v',B/'v7_sdb.v',S/'v7_sfd_candidate.v',D/'tb.sv',S/'tb_v7_sfd_candidate.sv'],'compile.log')
for top,passed in [('tb_v7_sdb','SDB_ALL_PASS'),('tb_v7_sfd_candidate','SFD_ALL_PASS')]:
 t=tool('vsim.exe',['-c','-vopt','-voptargs=+acc','work.'+top,'-do','onerror {quit -code 1}; run -all; quit -f'],top+'.log')
 assert passed in t and 'FAIL' not in t
fixture=(B/'fixture.vh').read_bytes();assert fixture.count(b'v7_sdb dut')==1
(D/'fixture.vh').write_bytes(fixture.replace(b'v7_sdb dut',b'v7_sdt_bus dut'))
tool('vlog.exe',['-sv',P/'v7_sdt_bus.v',D/'tb.sv'],'corrected_compile.log')
t=tool('vsim.exe',['-c','-vopt','-voptargs=+acc','work.tb_v7_sdb','-do','onerror {quit -code 1}; run -all; quit -f'],'corrected_bus.log')
assert 'SDB_ALL_PASS' in t and 'FAIL' not in t
print('BOTH_ORIGINAL_SUITES_PASS_IN_LOCAL_CANDIDATE')
