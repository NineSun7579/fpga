import json,shlex,sys
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root))
from audit import run,save
import board_ssh
code=r'''
import subprocess,json,os,glob,hashlib
exe='/userdata/detview-driving-demo/detview-driving-demo'
commands=[['readelf','-h',exe],['readelf','-n',exe],['readelf','-p','.comment',exe],['readelf','-d',exe],['readelf','--debug-dump=info',exe],['nm','-C',exe]]
result={'elf':[],'breadcrumbs':[],'sdk_readonly':{},'models':[]}
for cmd in commands:
 p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 out=p.stdout
 if cmd[0]=='nm': out='\n'.join(x for x in out.splitlines() if any(k in x.lower() for k in ['decode','infer','traffic','driving','scanmodel','canonical','rknn','geometry']))
 result['elf'].append({'argv':cmd,'rc':p.returncode,'stdout':out,'stderr':p.stderr})
p=subprocess.run(['strings','-a',exe],stdout=subprocess.PIPE,text=True)
result['breadcrumbs']=[x for x in p.stdout.splitlines() if any(k in x for k in ['detview-driving','/root/npu','/userdata','trafficlight','DET_','inference_geometry','driving_demo','native profile'])]
for path in ['/sys/module/rknpu/version','/sys/module/rknpu/srcversion','/sys/module/rknpu/parameters/version']:
 try: result['sdk_readonly'][path]=open(path).read()
 except Exception as e: result['sdk_readonly'][path]={'error':str(e)}
for directory in ['/root/npu/trafficlight','/root/npu/whiteboard_3cls']:
 for path in sorted(glob.glob(directory+'/*')):
  if not os.path.isfile(path): continue
  if not any(path.endswith(x) for x in ['.rknn','.json','.md','.txt']): continue
  h=hashlib.sha256()
  with open(path,'rb') as f:
   for b in iter(lambda:f.read(1048576),b''): h.update(b)
  result['models'].append({'path':path,'bytes':os.stat(path).st_size,'sha256':h.hexdigest()})
print(json.dumps(result))
'''
cli=board_ssh.connect()
try: save('elf_sdk_model_metadata.json',run(cli,code))
finally: cli.close()
