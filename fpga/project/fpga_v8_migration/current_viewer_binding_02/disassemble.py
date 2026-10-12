from pathlib import Path
import sys
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root))
from audit import run,save
import board_ssh
code=r'''
import subprocess,json
exe='/userdata/detview-driving-demo/detview-driving-demo'
symbols=subprocess.check_output(['nm',exe],text=True).splitlines()
selected=[s.split()[-1] for s in symbols if any(k in s for k in ['tryDecodeDfl','nmsAppend','7runOnce','10scanModels','6decodeE'])]
result=[]
for symbol in selected:
 p=subprocess.run(['objdump','-d','-C','--disassemble='+symbol,exe],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 # Use raw mangled names for selection; GNU objdump -C selection may use demangled names.
 if len(p.stdout.splitlines())<20:
  p=subprocess.run(['objdump','-d','--disassemble='+symbol,exe],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 result.append({'symbol':symbol,'rc':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
print(json.dumps(result))
'''
cli=board_ssh.connect()
try: save('compiled_codepaths.json',run(cli,code))
finally: cli.close()
