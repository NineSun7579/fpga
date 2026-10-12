from pathlib import Path
import os,sys,json,hashlib,subprocess,ctypes,time,re,traceback
E=Path(__file__).resolve().parent; P=Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
ARCH='set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,o):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:json.dump(o,f,indent=2)
def processes():
 return json.loads(subprocess.check_output(['powershell','-NoProfile','-Command','ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine) -Compress']))
def busy(ps):
 return [x for x in ps if x['Name'].lower() in {'pds.exe','pds_shell.exe','ta.exe','pne.exe','de.exe','pce.exe'} or (x.get('CommandLine') and any(t in x['CommandLine'] for t in ['run_diagnostic.py','continue_export.py','collect_native.py']) and x['ProcessId']!=os.getpid())]
def acquire(out):
 ps=processes();save(out/'before_mutex.json',dict(time=time.time(),busy=busy(ps),processes=ps))
 if busy(ps):raise RuntimeError('Global tools/controller busy; no mutex held, no tool started')
 k=ctypes.WinDLL('kernel32',use_last_error=True)
 k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];k.CreateMutexW.restype=ctypes.c_void_p
 k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint];k.WaitForSingleObject.restype=ctypes.c_uint
 k.ReleaseMutex.argtypes=[ctypes.c_void_p];k.CloseHandle.argtypes=[ctypes.c_void_p]
 h=k.CreateMutexW(None,False,'Global\\ov56401_PDS_single_instance')
 if not h:raise RuntimeError('Cannot open global mutex')
 r=k.WaitForSingleObject(h,0)
 if r not in (0,128):k.CloseHandle(h);raise RuntimeError('Mutex busy; zero wait; no tool started')
 ps=processes();save(out/'mutex_acquired.json',dict(time=time.time(),busy=busy(ps),processes=ps,wait_result=r))
 if busy(ps):k.ReleaseMutex(h);k.CloseHandle(h);raise RuntimeError('Global tools/controller busy after acquire')
 return k,h
def main(label,script):
 out=E/'probes'/label;out.mkdir(parents=True,exist_ok=False)
 k=h=None
 try:
  text=Path(script).read_text('ascii')
  if re.search(r'^\s*(?:compile|synthesize|syn|dev_map|pnr|gen_bit_stream|bit)\b',text,re.M):raise RuntimeError('Forbidden flow command')
  before={x['source']:x['sha256'] for x in json.loads((E/'copy_manifest.json').read_bytes())}
  before.update({x['copy']:x['sha256'] for x in json.loads((E/'copy_manifest.json').read_bytes())})
  if (E/'diagnostic_copy_manifest.json').exists():
   for x in json.loads((E/'diagnostic_copy_manifest.json').read_bytes())['files']:
    before[x['source']]=before[x['copy']]=x['sha256']
  assert all(sha(p)==v for p,v in before.items())
  save(out/'input_before.json',before)
  k,h=acquire(out)
  tool=P
  if label=='ta_help01':
   tool=P.with_name('ta.exe');cmd=[str(tool),'-help']
  elif label.startswith('ta_'):
   tool=P.with_name('ta.exe');cmd=[str(tool)]+json.loads((E/(label+'_argv.json')).read_bytes())
  else:cmd=[str(P),'-file',str(Path(script).resolve()),'-work_dir',str(out),'-project_name','v7_sdt_top']
  save(out/'launch.json',dict(argv=cmd,script_sha256=sha(script),tool_sha256=sha(tool),time=time.time(),pid=os.getpid()))
  with (out/'stdout.log').open('xb') as f:
   p=subprocess.Popen(cmd,cwd=out,stdout=f,stderr=subprocess.STDOUT)
   save(out/'process.json',dict(pid=p.pid,parent=os.getpid()))
   implicit=False;started=time.time();timed_out=False
   while p.poll() is None:
    raw=(out/'stdout.log').read_bytes()
    if re.search(rb'Executing\s*:\s*(?:compile|synthesize|dev_map|pnr)\b|Process\s+"(?:Compile|Synthesis|Device Map|Place.*Route)"\s+(?:start|begin)',raw,re.I):
     implicit=True;p.kill();break
    time.sleep(1)
    if label.startswith('ta_') and time.time()-started>45:timed_out=True;p.kill();break
   rc=p.wait()
  after={p:sha(p) for p in before};save(out/'input_after.json',after)
  raw=(out/'stdout.log').read_bytes()
  files=[dict(path=str(q),bytes=q.stat().st_size,sha256=sha(q)) for q in out.rglob('*') if q.is_file()]
  save(out/'receipt.json',dict(exit_code=rc,timed_out=timed_out,implicit_flow_detected=implicit,input_unchanged=after==before,raw_files=files,errors=[s.decode('utf-8','backslashreplace') for s in raw.splitlines() if re.search(rb'Timing-4006|STA-3016|\b(?:unknown|unresolved|unsupported|fatal)\b|^\s*E:|^\s*ERROR',s,re.I)]))
  print(label,'rc',rc,'implicit',implicit,'unchanged',after==before,flush=True)
 except BaseException:
  save(out/'failure.json',dict(traceback=traceback.format_exc(),time=time.time()));raise
 finally:
  if h:k.ReleaseMutex(h);k.CloseHandle(h)
if __name__=='__main__':main(sys.argv[1],sys.argv[2])
