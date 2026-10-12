from pathlib import Path
import os,sys,json,hashlib,shutil,subprocess,ctypes,time,re,traceback
sys.dont_write_bytecode=True
E=Path(__file__).resolve().parent; BOARD=E.parent
B=BOARD/'source_diagnostics_timing_build_04'; F=BOARD/'build04_final_route_runtime01'
D=BOARD/'build04_diagnostic_behavior_route01'; W=E/'work'
M=B/'evidence/runtime/mapping60_01/isolated_mapping_work/device_map'
PDS=Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
ARCH='set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def tree(p):return {str(q):sha(q) for q in p.rglob('*') if q.is_file()}
def save(n,o):
 p=E/n;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='ascii') as f:json.dump(o,f,indent=2,ensure_ascii=True)
def idle(label):
 ps=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command','ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine) -Compress']))
 busy=[p for p in ps if p['Name'].lower() in {'pds.exe','pds_shell.exe','ta.exe'}]
 save(label+'_idle.json',{'time':time.time(),'processes':ps,'busy':busy})
 if busy:raise RuntimeError('PDS/GUI/TA busy')
def guard(label):
 drift=[p for p,h in GUARD.items() if not Path(p).is_file() or sha(p)!=h]
 save('protection_'+label+'.json',{'count':len(GUARD),'drift':drift})
 if drift:raise RuntimeError('Protected source/stage drift')
def tool(label,text,cwd):
 idle(label);cwd.mkdir(parents=True,exist_ok=True)
 script=E/(label+'.tcl');script.write_text(text,encoding='ascii')
 if re.search(r'^\s*(?:compile|synthesize|syn|dev_map|gen_bit_stream|bit)\b',text,re.M):raise RuntimeError('Forbidden command')
 cmd=[str(PDS),'-file',str(script),'-work_dir',str(cwd),'-project_name','v7_sdt_top']
 save(label+'_toolcmd.json',{'argv':cmd,'cwd':str(cwd),'time':time.time(),'tool_sha256':sha(PDS),'script_sha256':sha(script),'mutex':'Global\\ov56401_PDS_single_instance'})
 log=E/(label+'.log');start=time.time();implicit=False
 with log.open('xb') as f:
  p=subprocess.Popen(cmd,cwd=cwd,stdout=f,stderr=subprocess.STDOUT)
  save(label+'_process.json',{'pid':p.pid,'controller_pid':os.getpid(),'time':start})
  print('REAL_TOOL_START '+label+' pid='+str(p.pid),flush=True)
  while p.poll() is None:
   raw=log.read_bytes()
   if re.search(rb'Executing\s*:\s*(?:compile|synthesize|dev_map)\b|Process\s+"(?:Compile|Synthesis|Device Map)"\s+(?:start|begin)',raw,re.I):
    implicit=True;p.kill();break
   time.sleep(2)
  rc=p.wait()
 raw=log.read_bytes()
 errors=[x.decode('ascii','backslashreplace') for x in raw.splitlines() if re.search(rb'Timing-4006|STA-3016|^\s*E:|^\s*(?:ERROR|FATAL)\b',x,re.I)]
 save(label+'_rawreceipt.json',{'rc':rc,'start':start,'end':time.time(),'log_sha256':sha(log),'errors':errors,'implicit_predecessor':implicit,'artifacts':tree(cwd)})
 guard('after_'+label);print('REAL_TOOL_FINISH '+label+' rc='+str(rc),flush=True)
 if implicit:raise RuntimeError('Implicit predecessor killed')
 return rc,raw
def main():
 global GUARD
 if W.exists():raise RuntimeError('Refuse existing execution directory')
 GUARD=tree(B);GUARD.update(tree(F));GUARD.update(tree(BOARD/'build04_timing_reload_probe01'))
 save('source_stage_hash_before.json',GUARD)
 for n in ['sourcehash.json','full_sourcehash.json','registration186.json']:
  shutil.copy2(D/n,E/n)
 shutil.copy2(F/'candidate_specific_expectation_contract.json',E/'candidate_specific_expectation_contract.json')
 idle('before_mutex')
 k=ctypes.WinDLL('kernel32',use_last_error=True)
 k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];k.CreateMutexW.restype=ctypes.c_void_p
 k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong];k.WaitForSingleObject.restype=ctypes.c_ulong
 k.ReleaseMutex.argtypes=[ctypes.c_void_p];k.CloseHandle.argtypes=[ctypes.c_void_p]
 h=k.CreateMutexW(None,False,'Global\\ov56401_PDS_single_instance')
 if not h:raise RuntimeError('Cannot create global mutex')
 wait=k.WaitForSingleObject(h,0)
 save('mutex.json',{'wait_result':wait,'pid':os.getpid(),'time':time.time()})
 if wait not in (0,128):k.CloseHandle(h);raise RuntimeError('Global mutex busy')
 try:
  idle('acquired');W.mkdir();copies=[]
  for source,dest in [(M,W/'device_map'),(F/'constraints',W/'constraints')]:
   shutil.copytree(source,dest)
   for q in source.rglob('*'):
    if q.is_file():
     c=dest/q.relative_to(source);copies.append({'source':str(q),'copy':str(c),'source_sha256':sha(q),'copy_sha256':sha(c)})
  save('copyhash_before.json',copies)
  if any(x['source_sha256']!=x['copy_sha256'] for x in copies):raise RuntimeError('Copy hash mismatch')
  adf=W/'device_map/v7_sdt_top_map.adf'
  if sha(adf)!='3a0478381bb9761f677937bf0a55374119fc2b6ce683d847d8a1dda2aacd5419':raise RuntimeError('ADF mismatch')
  names=['clock.fdc','cdc.fdc','ddr3.fdc','ov5640.fdc','pcie.fdc','sfp.fdc']
  text=ARCH+''.join('add_constraint {'+(W/'constraints'/n).as_posix()+'}\n' for n in names)
  text+='add_constraint {'+(W/'device_map/v7_sdt_top.pcf').as_posix()+'}\n'
  text+='pnr -force_to_run -input_db_file {'+adf.as_posix()+'} -optimize_multi_corner_timing -fix_hold_violation -report_timing\n'
  rc,raw=tool('pnr',text,W)
  routes=list((W/'place_route').glob('*.adf'))
  save('route_artifacts.json',{'rc':rc,'routes':{str(q):sha(q) for q in routes},'bit':False,'program':False})
  if rc or len(routes)!=1:raise RuntimeError('PNR failed or no unique routed ADF')
  route=routes[0];r='{'+route.as_posix()+'}'
  tool('native_graph',ARCH+'.switch_db -input '+r+' -output {'+(E/'routed_dump.txt').as_posix()+'}\n',E/'graph')
  tool('global10',ARCH+'report_timing -force_to_run -input_db_file '+r+' -delay_type max -max_path 10 -nworst 1 -report_exception TRUE\n',E/'reports/global10')
  tool('hold10',ARCH+'report_timing -force_to_run -input_db_file '+r+' -delay_type min -max_path 10 -nworst 1 -report_exception TRUE\n',E/'reports/hold10')
  save('copyhash_after.json',[dict(x,after_sha256=sha(x['copy'])) for x in copies])
 finally:
  guard('final');k.ReleaseMutex(h);k.CloseHandle(h)
if __name__=='__main__':
 try:main()
 except BaseException:
  save('failure.json',{'traceback':traceback.format_exc(),'time':time.time()});print(traceback.format_exc(),flush=True);sys.exit(1)
