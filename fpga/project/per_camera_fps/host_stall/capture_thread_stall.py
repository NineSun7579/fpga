"""One-session, read-only RK3568 scheduling capture; artifacts stay on host."""
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from board_host import ssh_connect

REMOTE = r'''
import os, glob, json, time, hashlib, shutil
def read(path):
 try:
  with open(path) as stream: return stream.read()
 except OSError: return None
def digest(path):
 try:
  with open(path,'rb') as stream: return hashlib.sha256(stream.read()).hexdigest()
 except OSError: return None
def emit(value): print(json.dumps(value,ensure_ascii=False),flush=True)
def stat(path):
 raw=read(path)
 if not raw: return None
 fields=raw[raw.rfind(')')+2:].split()
 return dict(name=raw[raw.find('(')+1:raw.rfind(')')],state=fields[0],ticks=int(fields[11])+int(fields[12]),start=fields[19],minflt=int(fields[7]),majflt=int(fields[9]),threads=int(fields[17]),rss_pages=int(fields[21]),cpu=int(fields[36]),raw=raw)
def processes():
 result={}
 for path in glob.glob('/proc/[0-9]*'):
  value=stat(path+'/stat')
  if value: result[path.split('/')[-1]]=value
 return result
def owners():
 result=[]
 for path in glob.glob('/proc/[0-9]*/fd/*'):
  try:
   target=os.readlink(path)
   if target.startswith('/dev/') and any(term in target for term in ('pango','xdma')):
    result.append(dict(pid=path.split('/')[2],fd=path.split('/')[-1],target=target))
  except OSError: pass
 return result
procs=processes()
candidates=[]
for pid in procs:
 cmd=read('/proc/'+pid+'/cmdline') or ''
 if cmd.split(chr(0))[0].rsplit('/',1)[-1].startswith(('detview','camview')): candidates.append(pid)
if len(candidates)!=1:
 emit(dict(kind='error',viewer_candidates=candidates)); raise SystemExit(2)
pid=candidates[0]; base='/proc/'+pid
def identity():
 value=stat(base+'/stat')
 if not value:return None
 cmd=read(base+'/cmdline') or ''
 argv=cmd.split(chr(0)); configs={}
 cwd=os.readlink(base+'/cwd')
 for arg in argv[1:]:
  path=arg if arg.startswith('/') else os.path.join(cwd,arg)
  try:
   if os.path.isfile(path) and os.path.getsize(path)<4*1024*1024: configs[path]=digest(path)
  except OSError: pass
 fds={}
 for path in glob.glob(base+'/fd/*'):
  try:fds[path.split('/')[-1]]=os.readlink(path)
  except OSError:pass
 return dict(pid=pid,start=value['start'],exe=os.readlink(base+'/exe'),exe_sha256=digest(base+'/exe'),argv=argv,config_sha256=configs,environ_sha256=digest(base+'/environ'),fds=fds,dma_owners=owners(),cgroup=read(base+'/cgroup'))
initial=identity()
logs=set(glob.glob('/userdata/linaro/100h_performance/pll56_*recovery.log'))
for target in initial['fds'].values():
 if target.endswith('.log'):logs.add(target)
positions={}
for path in logs:
 try:positions[path]=os.path.getsize(path)
 except OSError:pass
freqpaths=glob.glob('/sys/devices/system/cpu/cpufreq/policy*/scaling_cur_freq')+glob.glob('/sys/class/devfreq/*/cur_freq')
thermalpaths=glob.glob('/sys/class/thermal/thermal_zone*/temp')+glob.glob('/sys/class/thermal/thermal_zone*/type')
emit(dict(kind='start',time=time.time(),uptime=read('/proc/uptime'),identity=initial,hz=os.sysconf('SC_CLK_TCK'),kernel=read('/proc/version'),schedstats=read('/proc/sys/kernel/sched_schedstats'),schedstat_units='Linux /proc/PID/task/TID/schedstat: runtime nanoseconds, runnable wait nanoseconds, timeslices; zero wait is not proof of no wait if schedstats disabled',perf_path=shutil.which('perf'),perf_event_paranoid=read('/proc/sys/kernel/perf_event_paranoid'),initial_log_tail={path:(read(path) or '')[-12000:] for path in positions}))
start=time.monotonic()
for index in range(131):
 sample_start=time.monotonic()
 current=stat(base+'/stat')
 if not current or current['start']!=initial['start']:
  emit(dict(kind='identity_changed',time=time.time()));break
 threads={}
 paths=glob.glob(base+'/task/*')
 if len(paths)>200:emit(dict(kind='error',reason='thread cap exceeded'));break
 for path in paths:
  value=stat(path+'/stat')
  if not value:continue
  value.update(schedstat=read(path+'/schedstat'),wchan=read(path+'/wchan'),status=read(path+'/status'))
  if index in (0,130):value['sched']=read(path+'/sched')
  threads[path.split('/')[-1]]=value
 lognew={}
 for path,pos in list(positions.items()):
  try:
   size=os.path.getsize(path)
   with open(path,'rb') as stream:
    stream.seek(pos if size>=pos else 0); text=stream.read(256*1024)
    positions[path]=stream.tell()
   if text:lognew[path]=text.decode('utf-8','replace')
  except OSError:pass
 system={name:read('/proc/'+name) for name in ('stat','loadavg','meminfo','vmstat','interrupts','softirqs')}
 system['pressure']={name:read('/proc/pressure/'+name) for name in ('cpu','io','memory')}
 system['frequency']={path:read(path) for path in freqpaths}
 system['thermal']={path:read(path) for path in thermalpaths}
 system['cpuacct']={path:read(path) for path in glob.glob('/sys/fs/cgroup/cpuacct/cpuacct.*') if os.path.isfile(path)}
 emit(dict(kind='sample',index=index,time=time.time(),monotonic=time.monotonic(),uptime=read('/proc/uptime'),viewer_stat=current,viewer_status=read(base+'/status'),viewer_io=read(base+'/io'),threads=threads,processes=processes(),system=system,log_new=lognew,collector_cpu_seconds=time.process_time(),collector_work_seconds=time.monotonic()-sample_start))
 delay=start+index+1-time.monotonic()
 if index<130 and delay>0:time.sleep(delay)
emit(dict(kind='end',time=time.time(),uptime=read('/proc/uptime'),identity=identity(),collector_cpu_seconds=time.process_time()))
'''

def main():
    stamp = time.strftime('%Y%m%d_%H%M%S')
    out = ROOT.parent / 'log' / '100h_motion' / ('thread_stall_' + stamp + '.jsonl')
    progress = out.with_suffix('.progress.log')
    client = ssh_connect()
    stdin, stdout, stderr = client.exec_command('sudo -n python3 -u -', timeout=180)
    stdin.write(REMOTE)
    stdin.channel.shutdown_write()
    with out.open('w', encoding='utf-8') as raw, progress.open('w', encoding='utf-8') as monitor:
        for line in stdout:
            raw.write(line); raw.flush()
            value = json.loads(line)
            if value['kind'] != 'sample' or value['index'] % 10 == 0:
                message = json.dumps(dict(artifact=str(out),kind=value['kind'],index=value.get('index'),time=value.get('time'),pid=value.get('identity',{}).get('pid'),threads=len(value.get('threads',{})),log_bytes=sum(len(text) for text in value.get('log_new',{}).values())))
                print(message, flush=True); monitor.write(message+'\n'); monitor.flush()
    error = stderr.read().decode('utf-8','replace')
    code = stdout.channel.recv_exit_status()
    client.close()
    out.with_suffix('.stderr.log').write_text(error, encoding='utf-8')
    print(json.dumps(dict(artifact=str(out),exit_status=code)),flush=True)
    if code: raise SystemExit(code)

if __name__ == '__main__': main()
