"""Read-only board audit; all local outputs remain beside this script."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
REMOTE = r'''python3 - <<'PY'
import base64, datetime, glob, hashlib, json, os, subprocess
from pathlib import Path
def text(p):
    try: return Path(p).read_text().strip()
    except OSError: return None
def command(args):
    try:
        p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=40)
        return {'rc':p.returncode,'stdout':p.stdout.decode(errors='replace'),'stderr':p.stderr.decode(errors='replace')}
    except (OSError,subprocess.TimeoutExpired) as e: return {'error':str(e)}
def snapshot():
    owners=[]; errors=[]
    for root in glob.glob('/proc/[0-9]*'):
        fds=[]; maps=[]
        try:
            for fd in glob.glob(root+'/fd/*'):
                try:
                    target=os.readlink(fd)
                    if target.split(' (deleted)')[0]=='/dev/pango_pci_driver': fds.append({'fd':int(fd.rsplit('/',1)[1]),'target':target})
                except OSError: pass
            for line in Path(root+'/maps').read_text().splitlines():
                fields=line.split(None,5)
                if len(fields)==6 and fields[5].split(' (deleted)')[0]=='/dev/pango_pci_driver':
                    lo,hi=[int(v,16) for v in fields[0].split('-')]
                    maps.append({'line':line,'bytes':hi-lo,'file_offset':int(fields[2],16)})
            if not fds and not maps: continue
            stat=Path(root+'/stat').read_text(); start=stat[stat.rfind(')')+2:].split()[19]
            owners.append({'pid':int(root.rsplit('/',1)[1]),'starttime_ticks':start,'exe':os.readlink(root+'/exe'),'exe_sha256':hashlib.sha256(Path(root+'/exe').read_bytes()).hexdigest(),'fds':fds,'dma_mappings':maps})
        except OSError as e:
            if fds or maps: errors.append({'proc':root,'error':str(e)})
    module={k:text('/sys/module/pango_pci_driver/'+k) for k in ['srcversion','version','initstate','refcnt']}
    module['proc_modules_line']=next((x for x in (text('/proc/modules') or '').splitlines() if x.startswith('pango_pci_driver ')),None)
    return {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'boot_id':text('/proc/sys/kernel/random/boot_id'),'kernel':os.uname()._asdict() if hasattr(os.uname(),'_asdict') else list(os.uname()),'clock_ticks':os.sysconf('SC_CLK_TCK'),'owners':owners,'errors':errors,'module':module}
result={'read_only':True,'snapshot_1':snapshot(),'modinfo':command(['modinfo','pango_pci_driver'])}
paths=set()
filename=command(['modinfo','-F','filename','pango_pci_driver'])
result['modinfo_filename']=filename
if filename.get('rc')==0: paths.add(filename['stdout'].strip())
search=command(['find','/userdata','/home/linaro','/lib/modules','/usr/src','-type','f','(','-name','pango_pci_driver.c','-o','-name','pango_pci_driver.h','-o','-name','pango_pci_driver*.ko','-o','-name','pango_pci_driver.mod.c','-o','-name','.pango_pci_driver.ko.cmd','-o','-name','.pango_pci_driver.o.cmd',')'])
result['path_search']=search
paths.update(search.get('stdout','').splitlines())
files=[]
for name in sorted(paths)[:120]:
    try:
        p=Path(name); data=p.read_bytes()
        row={'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'mtime_ns':p.stat().st_mtime_ns}
        if len(data)<=4000000: row['base64']=base64.b64encode(data).decode()
        if name.endswith('.ko'):
            row['modinfo']=command(['modinfo',name]); row['elf']=command(['readelf','-n','-p','.modinfo','-p','.comment',name])
            strings=command(['strings',name])
            row['source_breadcrumbs']=[x for x in strings.get('stdout','').splitlines() if any(t in x for t in ['pango_pci_driver.c','/driver/','/usr/src','/home/','/userdata/','srcversion=','vermagic=','version='])][:100]
        files.append(row)
    except OSError as e: files.append({'path':name,'error':str(e)})
result['disk_files']=files
result['build_headers']={p:os.path.realpath(p) for p in ['/lib/modules/'+os.uname().release+'/build','/lib/modules/'+os.uname().release+'/source']}
result['snapshot_2']=snapshot()
print(json.dumps(result))
PY'''

def main():
    destination=ROOT/'board_evidence.json'
    if destination.exists(): raise FileExistsError(destination)
    spec=importlib.util.spec_from_file_location('board_connection',PROJECT/'board_ssh.py')
    helper=importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    client=helper.connect()
    try:
        rc,out,err=helper.run(client,REMOTE,timeout=240,sudo=True)
        if rc: raise RuntimeError('Read-only probe failed: '+err)
        result=json.loads(out)
        for i,row in enumerate(result['disk_files']):
            encoded=row.pop('base64',None)
            if encoded:
                target=ROOT/'board_files'/('%03d_'%i+Path(row['path']).name)
                target.parent.mkdir(exist_ok=True); target.write_bytes(base64.b64decode(encoded))
                row['local_evidence']=str(target.relative_to(ROOT))
        destination.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:result[k] for k in ['snapshot_1','snapshot_2']},indent=2))
        print('Disk file evidence count:',len(result['disk_files']))
    finally: client.close()

if __name__=='__main__': main()
