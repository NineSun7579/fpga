from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess,re
p=Path(__file__).resolve().parent
def run(name):
 r=subprocess.run(['C:/modeltech64_10.6e/win64/vsim.exe','-c','-do',name+'.do','-l',name+'.log'],cwd=p,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 s=(p/(name+'.log')).read_bytes()
 ok=r.returncode==0 and b'PASS REJECTION' in s and not re.search(rb'\*\* (Fatal|Error)',s)
 return name,ok,[x.decode() for x in s.splitlines() if b'PASS ' in x]
with ThreadPoolExecutor(max_workers=3) as pool:
 results=list(pool.map(run,['rejection_diag','rejection_diag_vendor','rejection_regs']))
text='\n'.join(str(x) for x in results)
(p/'rejection_suite.log').write_text(text)
print(text)
assert all(x[1] for x in results)
