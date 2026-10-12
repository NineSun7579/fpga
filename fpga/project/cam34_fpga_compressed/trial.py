"""Collect hardware-compressed C3/C4 evidence and actual sustained rates."""
from pathlib import Path
import importlib.util,json,shlex,time,argparse,hashlib
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('board',root.parent/'board_ssh.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
p=argparse.ArgumentParser();p.add_argument('action',choices=['launch','status','capture','collect','live']);p.add_argument('--seconds',type=int,default=120);a=p.parse_args()
evidence=root/'board_evidence';evidence.mkdir(exist_ok=True)
remote='/userdata/linaro/ov56401-cam34-wire-trial';m=json.loads((root/'viewer_build/manifest.json').read_bytes());c=b.connect()
def run(cmd,timeout=30):
 rc,o,e=b.run(c,cmd,timeout=timeout,sudo=True)
 if rc:raise RuntimeError('RC '+str(rc)+': '+o+e[-1000:])
 return o
try:
 if a.action in ['launch','live']:
  check="python3 -c 'import subprocess;from pathlib import Path;assert not subprocess.run([\"fuser\",\"/dev/pango_pci_driver\"],capture_output=True).stdout.strip();assert Path(\"/sys/module/pango_zc/refcnt\").read_text().strip()==\"0\"'"
  run(check);assert run('sha256sum '+shlex.quote(m['executable'])).split()[0]==m['executable_sha256']
  run('mkdir -p '+remote+'/input '+remote+'/tmp')
  cmd=['env','DISPLAY=:0','XAUTHORITY=/var/run/lightdm/root/:0','QT_QPA_PLATFORM=xcb','QT_XCB_GL_INTEGRATION=xcb_egl','TMPDIR='+remote+'/tmp','DETVIEW_FPGA_INFER_RGB=0','DETVIEW_CAM34_EVIDENCE_DIR='+remote+'/input','DETVIEW_CAM34_DETECTION_LOG=1',m['executable'],'--model','MVP_accuracy_round1','--fullscreen','--no-tracking','--detect-interval-ms','50','--detect-min-ms','50']
  name='runtime' if a.action=='launch' else 'live'
  if a.action=='launch':cmd+=['--duration',str(a.seconds)]
  run('nohup '+shlex.join(cmd)+' > '+remote+'/'+name+'.log 2>&1 < /dev/null & echo $! > '+remote+'/'+name+'.pid')
  row={'pid':int(run('cat '+remote+'/'+name+'.pid').strip()),'command':cmd,'seconds':a.seconds if a.action=='launch' else None,'sha256':m['executable_sha256'],'launched_at_local_unix':time.time()}
  (evidence/(name+'_launch.json')).write_text(json.dumps(row,indent=2),encoding='utf-8');print(json.dumps(row,indent=2))
 elif a.action=='status':
  print(run('if [ -f '+remote+'/runtime.pid ]; then ps -p "$(cat '+remote+'/runtime.pid)" -o pid,stat,pcpu,rss,comm; fi; tail -6 '+remote+'/runtime.log'))
 elif a.action=='capture':
  name='desktop_'+str(time.time_ns());run('env DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 xwd -root -silent -out '+remote+'/'+name+'.xwd')
  run('ffmpeg -y -i '+remote+'/'+name+'.xwd -frames:v 1 -update 1 '+remote+'/'+name+'.png 2> '+remote+'/screenshot_convert.log')
  with c.open_sftp()as sf:sf.get(remote+'/'+name+'.png',str(evidence/(name+'.png')))
  print(evidence/(name+'.png'))
 elif a.action=='collect':
  with c.open_sftp()as sf:
   sf.get(remote+'/runtime.log',str(evidence/'runtime.log'))
   for n in sf.listdir(remote+'/input'):
    if n.endswith(('.png','.json')):sf.get(remote+'/input/'+n,str(evidence/n))
  print('Collected',evidence)
finally:c.close()
