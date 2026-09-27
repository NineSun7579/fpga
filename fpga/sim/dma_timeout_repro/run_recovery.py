"""Run isolated ModelSim libraries; fail on assertions even if vsim exits 0."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess, re, sys, difflib
here=Path(__file__).resolve().parent
root=here.parents[1]
exe='C:/modeltech64_10.6e/win64/vsim.exe'
def run(name, expected):
 log=here/(name+'.log')
 result=subprocess.run([exe,'-c','-do',name+'.do','-l',str(log)],cwd=here,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 text=log.read_bytes()
 passed=result.returncode==0 and expected in text and not re.search(rb'\*\* (?:Fatal|Error)',text)
 return name,passed,[l.decode('ascii',errors='replace') for l in text.splitlines() if b'PASS ' in l]
jobs=[('frame_recovery',b'PASS FRAME RECOVERY success=10 abort=7 AW=61 B=61'),
      ('frame_recovery_vendor',b'PASS FRAME RECOVERY success=10 abort=7 AW=1425 B=1425'),
      ('ledger_recovery',b'PASS separate success/abort: cam1=5/0 cam2=1/0 cam3=0/2')]
with ThreadPoolExecutor(max_workers=3) as pool:
 results=list(pool.map(lambda pair:run(*pair),jobs))
ok=True;report=[]
for name,passed,lines in results:
 report.append(f'{name}: {"PASS" if passed else "FAIL"}')
 report.extend(lines);ok &= passed
audit=subprocess.run([sys.executable,'audit_recovery.py'],cwd=here,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
report.append(audit.stdout.decode('utf-8',errors='replace'));ok &= audit.returncode==0
diff=[]
for p in (root/'source').rglob('*.frame_recovery.bak'):
 current=p.with_name(p.name.removesuffix('.frame_recovery.bak'))
 diff.extend(difflib.unified_diff(p.read_bytes().decode('gbk',errors='replace').splitlines(True),current.read_bytes().decode('gbk',errors='replace').splitlines(True),fromfile=str(p.relative_to(root)),tofile=str(current.relative_to(root))))
(here/'recovery_source.diff').write_text(''.join(diff),encoding='utf-8')
report.append('OVERALL '+('PASS' if ok else 'FAIL'))
text='\n'.join(report)+'\n';(here/'recovery_suite.log').write_text(text,encoding='utf-8');print(text)
sys.exit(0 if ok else 1)
