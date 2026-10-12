import sys, json, hashlib, shlex, time, base64
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))
import board_ssh

REMOTE = r'''
import os, glob, json, hashlib, time
def text(p):
 try: return open(p).read()
 except Exception as e: return {'error':str(e)}
def link(p):
 try: return os.readlink(p)
 except Exception as e: return 'ERROR:'+str(e)
def sha(p):
 try:
  h=hashlib.sha256()
  with open(p,'rb') as f:
   for b in iter(lambda:f.read(1048576),b''): h.update(b)
  return h.hexdigest()
 except Exception as e: return 'ERROR:'+str(e)
result={'time':time.time(),'boot':text('/proc/sys/kernel/random/boot_id'),'kernel':text('/proc/version'),'uptime':text('/proc/uptime'),'processes':[],'scan_errors':[],'module':{}}
result['rknpu_version']=text('/sys/module/rknpu/version')
for key in ['refcnt','initstate','version','srcversion']:
 result['module'][key]=text('/sys/module/pango_pci_driver/'+key)
for d in glob.glob('/proc/[0-9]*'):
 try:
  exe=link(d+'/exe'); maps=text(d+'/maps'); fd=[]
  try:
   for f in os.listdir(d+'/fd'):
    target=link(d+'/fd/'+f)
    if '/dev/pango' in target.lower(): fd.append({'fd':f,'target':target})
  except Exception as e: result['scan_errors'].append({'pid':d,'fd_error':str(e)})
  lines=maps.splitlines() if isinstance(maps,str) else []
  pm=[x for x in lines if '/dev/pango' in x.lower()]; rm=[x for x in lines if 'rknn' in x.lower()]
  if fd or pm or ('detview' in exe):
   stat=text(d+'/stat'); fields=stat[stat.rfind(')')+2:].split() if isinstance(stat,str) else []
   cmd=open(d+'/cmdline','rb').read().replace(b'\0',b' ').decode('utf-8','replace')
   result['processes'].append({'pid':int(d.split('/')[-1]),'start_ticks':fields[19] if len(fields)>19 else None,'exe':exe,'exe_sha256':sha(d+'/exe'),'cwd':link(d+'/cwd'),'cmdline':cmd,'pango_fds':fd,'pango_maps':pm,'rknn_maps':rm,'stat_before':stat,'stat_after':text(d+'/stat'),'runtime_files':{x.split()[-1]:sha(x.split()[-1]) for x in rm if x.split()[-1].startswith('/')}})
  elif isinstance(maps,dict): result['scan_errors'].append({'pid':d,'maps_error':maps})
 except Exception as e: result['scan_errors'].append({'pid':d,'error':str(e)})
print(json.dumps(result))
'''

def run(cli, code):
    rc, out, err = board_ssh.run(cli, 'python3 -c '+shlex.quote(code), sudo=True)
    if rc: raise RuntimeError(f'remote read failed rc={rc}')
    return json.loads(out)

def save(name, value):
    (ROOT/name).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')

def main():
    cli=board_ssh.connect()
    try:
        if sys.argv[1]=='snapshot':
            save(sys.argv[2],run(cli,REMOTE))
        elif sys.argv[1]=='discover':
            code=r'''
import os,json
roots=['/userdata/linaro/detview-driving-demo-src','/userdata/detview-driving-demo']
files=[]
for root in roots:
 for d,ds,fs in os.walk(root):
  if d.count('/')-root.count('/')>=4: ds[:]=[]
  for f in fs:
   p=os.path.join(d,f)
   files.append({'path':p,'bytes':os.stat(p).st_size})
print(json.dumps({'roots':roots,'files':files}))
'''
            save('discovery.json',run(cli,code))
        elif sys.argv[1]=='pull':
            selection=json.loads((ROOT/'selection.json').read_text())
            code='import json,hashlib,os\npaths='+repr(selection)+'''\nresult=[]
for p in paths:
 try:
  h=hashlib.sha256()
  with open(p,'rb') as f:
   for b in iter(lambda:f.read(1048576),b''): h.update(b)
  st=os.stat(p)
  result.append({'path':p,'sha256':h.hexdigest(),'bytes':st.st_size,'mtime_ns':st.st_mtime_ns})
 except Exception as e: result.append({'path':p,'error':str(e)})
print(json.dumps(result))
'''
            before=run(cli,code); save('remote_hash_before.json',before)
            sftp=cli.open_sftp(); manifest=[]
            try:
                for entry in before:
                    if 'error' in entry: manifest.append(entry); continue
                    p=entry['path']; target=ROOT/'inputs'/p.lstrip('/')
                    target.parent.mkdir(parents=True,exist_ok=True)
                    try:
                        sftp.get(p,str(target))
                    except Exception as error:
                        if p.startswith('/root/npu/'):
                            value=run(cli,'import base64,json\nprint(json.dumps(base64.b64encode(open('+repr(p)+',"rb").read()).decode()))')
                            target.write_bytes(base64.b64decode(value))
                            manifest.append({**entry,'local':str(target.relative_to(ROOT)),'local_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'retrieval':'SSH sudo ordinary file read; SFTP permission denied'})
                            continue
                        manifest.append({**entry,'download_error':str(error)})
                        if target.exists(): target.unlink()
                        continue
                    manifest.append({**entry,'local':str(target.relative_to(ROOT)),'local_sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
            finally: sftp.close()
            after=run(cli,code); save('remote_hash_after.json',after)
            lookup={e['path']:e for e in after}
            for e in manifest:
                e['remote_after']=lookup.get(e['path'])
                e['stable_match']=e.get('sha256')==e.get('local_sha256')==lookup.get(e['path'],{}).get('sha256') and 'sha256' in e
            save('retrieval_manifest.json',manifest)
    finally: cli.close()
if __name__=='__main__': main()
