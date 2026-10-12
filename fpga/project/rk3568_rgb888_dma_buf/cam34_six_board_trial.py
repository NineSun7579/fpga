"""Run the isolated C3/C4 viewer and collect real RK3568 evidence."""
import argparse,json,shlex,sys,time,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
root=Path(__file__).resolve().parent
remote='/userdata/linaro/ov56401-cam34-six-shared-20261010'
p=argparse.ArgumentParser();p.add_argument('action',choices=['launch','status','collect','capture']);p.add_argument('--manifest',type=Path);p.add_argument('--seconds',type=int,default=90);p.add_argument('--model',default='MVP_accuracy_round1');a=p.parse_args()
local=root/'cam34_six_board_evidence';local.mkdir(exist_ok=True)
c=board_ssh.connect()
def run(cmd,sudo=True):
 rc,o,e=board_ssh.run(c,cmd,timeout=30,sudo=sudo)
 if rc:raise RuntimeError(f'RC {rc}: '+o+e[-1000:])
 return o
try:
 if a.action=='launch':
  m=json.loads(a.manifest.read_bytes());exe=m['executable']
  owners=run("fuser /dev/pango_pci_driver 2>/dev/null || true").strip()
  if owners:raise RuntimeError('Existing device owner: '+owners)
  check="python3 -c 'import os; fd=os.open(\"/dev/pango_pci_driver\",os.O_RDWR|os.O_SYNC); os.close(fd); print(\"DEVICE_OPEN_OK\")'"
  print(run(check).strip())
  sha=run('sha256sum '+shlex.quote(exe)).split()[0]
  if sha!=m['executable_sha256']:raise RuntimeError('Binary hash mismatch')
  run('mkdir -p '+remote+'/input '+remote+'/tmp')
  command=['env','DISPLAY=:0','XAUTHORITY=/var/run/lightdm/root/:0','QT_QPA_PLATFORM=xcb','QT_XCB_GL_INTEGRATION=xcb_egl','TMPDIR='+remote+'/tmp','DETVIEW_CAM34_EVIDENCE_DIR='+remote+'/input','DETVIEW_CAM34_DETECTION_LOG=1',exe,'--model',a.model,'--fullscreen','--no-tracking','--detect-interval-ms','50','--detect-min-ms','50']
  if a.seconds:command+=['--duration',str(a.seconds)]
  cmd='nohup '+shlex.join(command)+' > '+remote+'/runtime.log 2>&1 < /dev/null & echo $! > '+remote+'/viewer.pid'
  run(cmd)
  pid=run('cat '+remote+'/viewer.pid').strip()
  info={'remote':remote,'pid':int(pid),'executable':exe,'sha256':sha,'argv':command,'model':a.model,'seconds':a.seconds,'launched_at_local_unix':time.time(),'manifest':str(a.manifest)}
  (local/'launch.json').write_text(json.dumps(info,indent=2),encoding='utf-8');print(json.dumps(info,indent=2))
 elif a.action=='status':
  print(run('if [ -f '+remote+'/viewer.pid ]; then ps -p "$(cat '+remote+'/viewer.pid)" -o pid,stat,pcpu,rss,comm; fi; tail -8 '+remote+'/runtime.log'))
 elif a.action=='capture':
  filename='desktop_'+str(time.time_ns())
  run('env DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 xwd -root -silent -out '+remote+'/'+filename+'.xwd')
  run('ffmpeg -y -i '+remote+'/'+filename+'.xwd -frames:v 1 -update 1 '+remote+'/'+filename+'.png 2> '+remote+'/screenshot_convert.log')
  with c.open_sftp() as s:s.get(remote+'/'+filename+'.png',str(local/(filename+'.png')))
  print(local/(filename+'.png'))
 elif a.action=='collect':
  with c.open_sftp() as s:
   s.get(remote+'/runtime.log',str(local/'runtime.log'))
   try:
    for name in s.listdir(remote+'/input'):
     if name.endswith('.png'):s.get(remote+'/input/'+name,str(local/name))
   except OSError:pass
  print('Collected',local)
finally:c.close()
