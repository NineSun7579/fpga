import sys, json, time, pathlib, hashlib
sys.path.insert(0, str(pathlib.Path('project/tools').resolve()))
from board_host import ssh_connect

REMOTE = r'''
import os,glob,json,time,hashlib
def read(p):
 try:
  with open(p) as f:return f.read()
 except Exception as e:return 'UNAVAILABLE: '+str(e)
def procs():
 out={}
 for d in glob.glob('/proc/[0-9]*'):
  try:
   raw=read(d+'/stat'); a=raw[raw.rfind(')')+2:].split()
   out[d.split('/')[-1]]={'comm':read(d+'/comm').strip(),'cmd':read(d+'/cmdline').replace(chr(0),' '),'state':a[0],'ticks':int(a[11])+int(a[12]),'start':a[19],'threads':a[17], 'rss_pages':a[21]}
  except:pass
 return out
def snap():
 return {'time':time.time(),'uptime':read('/proc/uptime'),'stat':read('/proc/stat'),'interrupts':read('/proc/interrupts'),'softirqs':read('/proc/softirqs'),'load':read('/proc/loadavg'),'mem':read('/proc/meminfo'),'vmstat':read('/proc/vmstat'),'pressure':{p:read('/proc/pressure/'+p) for p in ['cpu','io','memory']},'freq':{p:read(p).strip() for p in glob.glob('/sys/devices/system/cpu/cpufreq/policy*/*') if p.rsplit('/',1)[-1] in ['scaling_cur_freq','scaling_governor','scaling_min_freq','scaling_max_freq','cpuinfo_max_freq']},'thermal':{p:read(p).strip() for p in glob.glob('/sys/class/thermal/thermal_zone*/*') if p.rsplit('/',1)[-1] in ['type','temp']},'devfreq':{p:read(p).strip() for p in glob.glob('/sys/class/devfreq/*/*') if p.rsplit('/',1)[-1] in ['cur_freq','governor','min_freq','max_freq']},'procs':procs()}
a=snap();time.sleep(30);b=snap()
hz=os.sysconf('SC_CLK_TCK');elapsed=b['time']-a['time'];heavy=[]
for pid,p in b['procs'].items():
 if pid in a['procs'] and p['start']==a['procs'][pid]['start']:
  heavy.append(dict(pid=pid,cpu_percent=round(100*(p['ticks']-a['procs'][pid]['ticks'])/hz/elapsed,2),**p))
heavy.sort(key=lambda p:p['cpu_percent'],reverse=True)
viewers={};owners=[]
for pid,p in b['procs'].items():
 if '/detview ' in p['cmd'] or '/camview ' in p['cmd']:
  d='/proc/'+pid;v={'process':p,'status':read(d+'/status'),'sched':read(d+'/sched'),'exe':os.readlink(d+'/exe'),'threads':{t.split('/')[-1]:{'stat':read(t+'/stat'),'schedstat':read(t+'/schedstat'),'comm':read(t+'/comm'),'wchan':read(t+'/wchan')} for t in glob.glob(d+'/task/*')}}
  v['exe_sha256']=hashlib.sha256(open(d+'/exe','rb').read()).hexdigest()
  env=read(d+'/environ').split(chr(0));v['env']=[x for x in env if x.startswith(('DETVIEW_','CAMVIEW_','QT_','OMP_','OPENBLAS_','OPENCV_','DISPLAY=','LIBGL_','MESA_'))]
  v['fds']={}
  for f in glob.glob(d+'/fd/*'):
   try:v['fds'][f]=os.readlink(f)
   except:pass
  viewers[pid]=v
 for f in glob.glob('/proc/'+pid+'/fd/*'):
  try:
   target=os.readlink(f)
   if 'pango' in target or 'xdma' in target:owners.append({'pid':pid,'comm':p['comm'],'fd':f,'target':target})
  except:pass
logs={}
for p in glob.glob('/userdata/linaro/100h_performance/pll56_*recovery.log'):
 logs[p]=read(p)[-60000:]
source=read('/userdata/linaro/detview-calibration-work/src/main.cpp')
terms=['setNumThreads','omp_','OPENBLAS','DETVIEW_QT_IDLE','QT_IDLE','GPU','copy_ms','read_ms','copyMs','readMs','thread','stereoInterval']
lines=source.splitlines();matches=[]
for i,line in enumerate(lines):
 if any(t in line for t in terms):matches.append({'line':i+1,'text':'\n'.join(lines[max(0,i-2):i+3])})
print(json.dumps({'sample_seconds':elapsed,'hz':hz,'before':a,'after':b,'top_cpu':heavy[:25],'viewers':viewers,'dma_owners':owners,'recovery_logs':logs,'source_matches':matches},ensure_ascii=False))
'''
cli=ssh_connect()
stdin,stdout,stderr=cli.exec_command('sudo -n python3 -',timeout=90)
stdin.write(REMOTE);stdin.channel.shutdown_write()
result=stdout.read().decode();err=stderr.read().decode();cli.close()
data=json.loads(result);data['ssh_stderr']=err
out=pathlib.Path('log/100h_motion/readonly_diagnosis_20261004.json')
out.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'report':str(out),'sample_seconds':data['sample_seconds'],'top_cpu':data['top_cpu'][:8],'viewers':{k:{'process':v['process'],'env':v['env'],'exe_sha256':v['exe_sha256']} for k,v in data['viewers'].items()},'dma_owners':data['dma_owners'],'freq':data['after']['freq'],'thermal':data['after']['thermal'],'devfreq':data['after']['devfreq'],'load':data['after']['load']},indent=2))
