"""Read-only, bounded board provenance capture; never opens a DMA device."""
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'tools'))
from board_host import ssh_connect

COMMAND = r'''sudo -n python3 - <<'PY'
import pathlib, hashlib, json, os, subprocess
def digest(p):
 try: return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
 except Exception as e: return str(e)
out={'viewers':[], 'files':[], 'modules':{}}
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit(): continue
 try:
  argv=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  exe=os.readlink(str(p/'exe'))
  if 'detview' not in exe: continue
  out['viewers'].append({'pid':int(p.name),'argv':argv,'exe':exe,'sha256':digest(p/'exe'),'stat':(p/'stat').read_text()})
 except Exception: pass
for p in pathlib.Path('/sys/module').glob('*pango*'):
 out['modules'][p.name]={}
 for name in ('version','srcversion','taint'):
  try: out['modules'][p.name][name]=(p/name).read_text()
  except Exception: pass
roots=['/userdata/linaro/detview-calibration-work','/userdata/detview-hdmifull','/root/npu/driver','/userdata/driver']
for root in roots:
 base=pathlib.Path(root)
 if not base.exists(): continue
 for p in base.rglob('*'):
  if not p.is_file(): continue
  rel=str(p.relative_to(base))
  if any(x in p.parts for x in ('.git','CMakeFiles')): continue
  selected=(p.suffix in ('.cpp','.h','.hpp','.c','.json','.txt','.pro') or 'receipt' in p.name or 'manifest' in p.name or p.name in ('Makefile','detview','detview-hdmifull'))
  if not selected or p.stat().st_size>2000000: continue
  record={'path':str(p),'sha256':digest(p),'size':p.stat().st_size}
  if p.suffix in ('.cpp','.h','.hpp','.c') or 'receipt' in p.name or 'manifest' in p.name or p.name=='CMakeCache.txt':
   record['text']=p.read_text(errors='replace')
  out['files'].append(record)
out['driver_discovery']=subprocess.run(['find','/root','/userdata','/home/linaro','-type','f','-name','pango_pci_driver*'],capture_output=True,text=True,timeout=20).stdout
for name in out['driver_discovery'].splitlines():
 p=pathlib.Path(name)
 record={'path':name,'sha256':digest(p),'size':p.stat().st_size}
 if p.suffix in ('.c','.h'): record['text']=p.read_text(errors='replace')
 if p.suffix=='.ko': record['modinfo']=subprocess.run(['modinfo',name],capture_output=True,text=True).stdout
 out['files'].append(record)
out['dmesg_tail']=subprocess.run(['dmesg'],capture_output=True,text=True).stdout.splitlines()[-300:]
out['uname']=subprocess.run(['uname','-a'],capture_output=True,text=True).stdout
print(json.dumps(out))
PY'''

def main():
    target = pathlib.Path(__file__).with_name('board_provenance_readonly.json')
    print('Read-only SSH provenance capture starting', flush=True)
    client = ssh_connect()
    try:
        _, stdout, stderr = client.exec_command(COMMAND, timeout=45)
        payload = stdout.read().decode()
        error = stderr.read().decode()
        if not payload.strip():
            target.write_text(json.dumps({'error': error, 'stdout': payload}), encoding='utf-8')
            print(error, flush=True)
            return
        result = json.loads(payload)
        result['local_capture_unix_s'] = time.time()
        result['stderr'] = error
        target.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps({'viewers': result['viewers'], 'modules': result['modules'],
                          'files': [{k:v for k,v in f.items() if k!='text'} for f in result['files']]}), flush=True)
    finally:
        client.close()

if __name__ == '__main__':
    main()
