"""Read only desktop environment paths and prior demo identities; no DMA or launch."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'tools'))
from board_host import ssh_connect, board_host

COMMAND = r"""python3 - <<'PY'
import glob, hashlib, json, os
files = ['/userdata/detview-driving-demo/detview-driving-demo',
 '/root/npu/trafficlight/det-yolov8n-trafficlight-16cls-640x480-rk3568-raw-dfl6-int8.rknn',
 '/root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v4_combo-rk3568-raw-dfl6-int8.rknn']
artifacts=[]
for name in files:
 try:
  h=hashlib.sha256()
  with open(name,'rb') as f:
   for block in iter(lambda:f.read(1048576),b''):h.update(block)
  artifacts.append({'path':name,'bytes':os.stat(name).st_size,'sha256':h.hexdigest()})
 except OSError as e:artifacts.append({'path':name,'error':type(e).__name__})
desktop=[]
for base in glob.glob('/proc/[0-9]*'):
 try:
  comm=open(base+'/comm').read().strip()
  if comm not in ('xfce4-session','xfdesktop','lxsession','mate-session','gnome-session-b','detview-driving'):continue
  env={}
  for item in open(base+'/environ','rb').read().split(b'\0'):
   key,sep,val=item.partition(b'=')
   if sep and key in (b'DISPLAY',b'XAUTHORITY'):env[key.decode()]=val.decode(errors='replace')
  desktop.append({'pid':int(base.rsplit('/',1)[1]),'comm':comm,'uid':os.stat(base).st_uid,
                  'environment_paths':env,'executable':os.readlink(base+'/exe')})
 except OSError:pass
print(json.dumps({'boot_id':open('/proc/sys/kernel/random/boot_id').read().strip(),
                 'artifacts':artifacts,'desktop_processes':desktop}))
PY
"""

client=ssh_connect()
try:
    _,stdout,stderr=client.exec_command(COMMAND,timeout=30)
    raw=stdout.read().decode();errors=stderr.read().decode()
    status=stdout.channel.recv_exit_status()
finally:
    client.close()
result={'host':board_host(),'captured_utc':datetime.now(timezone.utc).isoformat(),
        'exit_code':status,'stderr':errors,'observations':json.loads(raw),
        'dma_opened':False,'viewer_launched':False,'authority_contents_read':False}
(HERE/'viewer_recovery_identity03.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
