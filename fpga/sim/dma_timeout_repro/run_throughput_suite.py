"""Fresh logs, separate libraries, assertions checked independently of exit code."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess,re,sys
p=Path(__file__).resolve().parent
exe='C:/modeltech64_10.6e/win64/vsim.exe'
jobs=[]
def add(name,script,marker):
 (p/(name+'.do')).write_bytes(script)
 jobs.append((name,marker))
b=(p/'throughput.do').read_bytes().replace(b'work_throughput',b'work_throughput_original')
for f in ['axi_dma/axi_dma_write.v','ov5640/ov5640_ddr/ov5640_ddr.v','ov5640/ov5640_ddr/ov5640_ddr_w.v']:
 b=b.replace(('../../source/'+f).encode(),('../../source/'+f+'.burst_credit.bak').encode())
add('throughput_original',b,b'PASS throughput')
add('throughput_original_actual',b.replace(b'work_throughput_original',b'work_throughput_original_actual').replace(b'.tb_throughput\n',b'.tb_throughput -gAXI_RATE4=525\n'),b'PASS throughput')
b=(p/'throughput_fixed.do').read_bytes()
add('throughput_actual',b.replace(b'work_throughput',b'work_throughput_actual').replace(b'+FRAMES=3',b'+FRAMES=2 -gAXI_RATE4=525'),b'PASS throughput')
add('throughput_phase',b.replace(b'work_throughput',b'work_throughput_phase').replace(b'+FRAMES=3',b'+FRAMES=2 +PHASE=1137'),b'PASS throughput')
add('throughput_stress',b.replace(b'work_throughput',b'work_throughput_stress').replace(b'+FRAMES=3',b'+FRAMES=2 +LATENCY=64 +GAP=2 +PHASE=1975'),b'PASS throughput')
for name in ['frame_recovery','frame_recovery_vendor','ledger_recovery','credit_recovery','rejection_diag','rejection_diag_vendor','rejection_regs']:
 b=(p/(name+'.do')).read_bytes()
 # These established libraries are independent of the throughput simulations.
 add('throughput_regress_'+name,b,b'PASS')
def run(job):
 name,marker=job
 if len(sys.argv)==1 or name in sys.argv[1:]:
  result=subprocess.run([exe,'-c','-do',name+'.do','-l',name+'.log'],cwd=p,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  returncode=result.returncode
 else:
  returncode=0
 text=(p/(name+'.log')).read_bytes()
 ok=returncode==0 and marker in text and not re.search(rb'\*\* (?:Error|Fatal)',text)
 lines=[line.decode('ascii','replace') for line in text.splitlines() if any(s in line for s in [b'PASS ',b'RESULT ',b'PERF ',b'REJECT ',b'** Fatal',b'** Error'])]
 return name,ok,lines
report=[];ok=True
with ThreadPoolExecutor(max_workers=3) as pool:
 for future in as_completed([pool.submit(run,j) for j in jobs]):
  name,passed,lines=future.result();ok &= passed
  chunk=name+': '+('PASS' if passed else 'FAIL')+'\n'+'\n'.join(lines)
  print(chunk,flush=True);report.append(chunk)
report.append('OVERALL '+('PASS' if ok else 'FAIL'))
(p/'throughput_suite.log').write_bytes(('\n'.join(report)+'\n').encode())
sys.exit(0 if ok else 1)
