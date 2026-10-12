from pathlib import Path
import sys,os,json,hashlib,shutil,subprocess,ctypes,time,re,traceback
sys.dont_write_bytecode=True
E=Path(__file__).resolve().parent; BOARD=E.parent; B=BOARD/'source_diagnostics_timing_build_04'
M=B/'evidence/runtime/mapping60_01'; W=E/'work'
PDS=Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
sys.path[:0]=[str(B/'runtime'),str(B/'runtime/libraries'),str(B/'runtime/analysis_tools')]
import preflight
def sha(p):return preflight.sha(p)
def save(n,o):
 p=E/n;p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():raise RuntimeError('Refuse overwrite '+str(p))
 p.write_text(json.dumps(o,indent=2,ensure_ascii=True)+'\n',encoding='ascii')
def load(p):return json.loads(Path(p).read_bytes())
def tree(p):return {str(q):sha(q) for q in p.rglob('*') if q.is_file()}
def guard(label):
 drift=[p for p,h in GUARD.items() if not Path(p).is_file() or sha(p)!=h]
 save('protection_'+label+'.json',{'fixed_files':len(GUARD),'drift':drift,'new_files_excluded':True})
 if drift:raise RuntimeError('Fixed input drift')
def idle(label):
 ps=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command','ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine) -Compress']))
 busy=[p for p in ps if p['Name'].lower() in {'pds.exe','pds_shell.exe','ta.exe'}]
 save(label+'_idle.json',{'time':time.time(),'processes':ps,'busy':busy})
 if busy:raise RuntimeError('PDS/GUI/TA busy')
def tool(label,text,cwd):
 idle(label);script=E/(label+'.tcl');script.write_text(text,encoding='ascii')
 if re.search(r'^\s*(?:compile|synthesize|syn|dev_map|gen_bit_stream|bit)\b',text,re.M):raise RuntimeError('Forbidden command')
 cmd=[str(PDS),'-file',str(script),'-work_dir',str(cwd),'-project_name','v7_sdt_top']
 save(label+'_launch.json',{'command':cmd,'controller_pid':os.getpid(),'cwd':str(cwd),'time':time.time(),'tool_sha256':sha(PDS),'script_sha256':sha(script),'mutex':'Global\\ov56401_PDS_single_instance'})
 log=E/(label+'.log');print('REAL_TOOL_START '+label,flush=True)
 with log.open('xb') as f:
  p=subprocess.Popen(cmd,cwd=cwd,stdout=f,stderr=subprocess.STDOUT)
  save(label+'_process.json',{'pid':p.pid,'controller_pid':os.getpid(),'time':time.time()})
  implicit=False
  while p.poll() is None:
   raw=log.read_bytes()
   if label=='pnr' and re.search(rb'(?:Executing\s*:\s*(?:compile|synthesize|dev_map)\b|Process\s+"(?:Compile|Synthesis|Synthesize|Device Map|DevMap)"\s+(?:start|begin))',raw,re.I):
    implicit=True;p.kill();break
   time.sleep(2)
  code=p.wait()
 raw=log.read_bytes();lines=raw.splitlines()
 bad=[x.decode('ascii','backslashreplace') for x in lines if re.search(rb'Timing-4006|STA-3016|\b(?:unknown|unresolved|unrecognized|unsupported|fatal)\b|^\s*E:|^\s*(?:ERROR|FATAL)\b',x,re.I)]
 native_logs={str(q):{'sha256':sha(q),'error_lines':[x.decode('ascii','backslashreplace') for x in q.read_bytes().splitlines() if re.search(rb'Timing-4006|STA-3016|\b(?:unknown|unresolved|fatal)\b|^\s*E:',x,re.I)]} for q in cwd.rglob('run.log') if not any(s in q.parts for s in ['compile','synthesize','device_map'])}
 save(label+'_receipt.json',{'exit_code':code,'raw_errors':bad,'native_logs':native_logs,'implicit_predecessor_detected':implicit,'log_sha256':sha(log),'time':time.time(),'files':tree(cwd)})
 print('REAL_TOOL_FINISH '+label+' exit='+str(code),flush=True)
 guard('after_'+label)
 if implicit:raise RuntimeError('Implicit predecessor rerun detected and killed; no retry')
 return code,raw
ARCH='set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'
def main():
 global GUARD
 if W.exists():raise RuntimeError('One attempt only')
 m=preflight.verify()
 roots=[B,BOARD/'source_diagnostics_timing_build_03',BOARD/'source_diagnostics_timing_build_02',BOARD/'build04_mapped_endpoint_review02',BOARD/'build04_official_behavior_export01']
 GUARD={p:h for r in roots for p,h in tree(r).items()};GUARD.update({p:sha(p) for p in m['protected_hashes']})
 save('protection_before.json',GUARD);save('sourcehash.json',m['local_hashes']);save('full_sourcehash.json',m['full_source_copy_hashes']);save('registration186.json',m['registered_sources'])
 idle('before_mutex')
 k=ctypes.WinDLL('kernel32',use_last_error=True);k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];k.CreateMutexW.restype=ctypes.c_void_p;k.ReleaseMutex.argtypes=[ctypes.c_void_p];k.CloseHandle.argtypes=[ctypes.c_void_p]
 h=k.CreateMutexW(None,True,'Global\\ov56401_PDS_single_instance');exists=ctypes.get_last_error()==183
 if not h or exists:
  if h:k.CloseHandle(h)
  raise RuntimeError('Global mutex busy')
 try:
  idle('mutex_acquired');W.mkdir()
  copies=[]
  for d in ['compile','synthesize','rtl','inputs','constraints_live']:
   shutil.copytree(B/d,W/d)
   for q in (B/d).rglob('*'):
    if q.is_file():
     c=W/q.relative_to(B);copies.append({'source':str(q),'copy':str(c),'source_sha256':sha(q),'copy_sha256':sha(c)})
  shutil.copy2(B/'project.pds',W/'project.pds')
  shutil.copytree(M/'isolated_mapping_work/device_map',W/'device_map')
  for q in (M/'isolated_mapping_work/device_map').rglob('*'):
   if q.is_file():
    c=W/'device_map'/q.relative_to(M/'isolated_mapping_work/device_map');copies.append({'source':str(q),'copy':str(c),'source_sha256':sha(q),'copy_sha256':sha(c)})
  copies.append({'source':str(B/'project.pds'),'copy':str(W/'project.pds'),'source_sha256':sha(B/'project.pds'),'copy_sha256':sha(W/'project.pds')})
  if not all(x['source_sha256']==x['copy_sha256'] for x in copies):raise RuntimeError('Copy mismatch')
  save('copyhash.json',copies)
  adf=W/'device_map/v7_sdt_top_map.adf'
  if sha(adf)!='3a0478381bb9761f677937bf0a55374119fc2b6ce683d847d8a1dda2aacd5419':raise RuntimeError('Mapped ADF mismatch')
  helpdir=E/'help';helpdir.mkdir();code,raw=tool('help',ARCH+'help pnr\n',helpdir)
  if code or b'-input_db_file' not in raw:raise RuntimeError('PNR help unavailable')
  text=ARCH+''.join('add_constraint {'+(W/'constraints_live'/n).as_posix()+'}\n' for n in ['clock.fdc','cdc.fdc','ddr3.fdc','ov5640.fdc','pcie.fdc','sfp.fdc'])
  text+='add_constraint {'+(W/'device_map/v7_sdt_top.pcf').as_posix()+'}\n'
  text+='pnr -force_to_run -input_db_file {'+adf.as_posix()+'} -optimize_multi_corner_timing -fix_hold_violation\n'
  code,raw=tool('pnr',text,W)
  routes=[q for q in (W/'place_route').glob('*.adf') if q.stat().st_size]
  prr=W/'place_route/prr.db'
  save('route_artifacts.json',{'adfs':{str(q):sha(q) for q in routes},'prr_sha256':sha(prr) if prr.is_file() else None,'pnr_exit_code':code,'done_lines':[x.decode('ascii','backslashreplace') for x in raw.splitlines() if b'done' in x.lower()],'diagnostic_only':True})
  if len(routes)!=1 or not prr.is_file() or not prr.stat().st_size:raise RuntimeError('No unique actual routed ADF and nonzero native prr')
  route=routes[0]
  if code!=0:raise RuntimeError('PNR tool failed; artifacts retained; inspect raw/native errors')
  export=E/'functional';export.mkdir()
  code,raw=tool('functional',ARCH+'gen_netlist -force_to_run -input_db_file {'+route.as_posix()+'} -func_sim_only -sdf_annotate FALSE\n',export)
  graphs=E/'routed';(graphs/'synthesis_export').mkdir(parents=True);(graphs/'analysis').mkdir()
  code2,raw2=tool('graph',ARCH+'.switch_db -input {'+route.as_posix()+'} -output {'+(graphs/'synthesis_export/synthesis_dump.txt').as_posix()+'}\n',graphs)
  parser=B/'runtime/analysis_tools/parse_objects.py';shutil.copy2(parser,graphs/'analysis/parse_objects.py')
  res=subprocess.run([sys.executable,'-B',str(graphs/'analysis/parse_objects.py')],cwd=graphs/'analysis',capture_output=True);(graphs/'analysis/parser.log').write_bytes(res.stdout+res.stderr)
  save('export_result.json',{'functional_exit':code,'graph_exit':code2,'parser_exit':res.returncode,'routed_adf':str(route),'routed_sha256':sha(route),'functional_files':tree(export),'graph_files':tree(graphs),'parser_source_sha256':sha(parser),'diagnostic_only':True,'final_timing_acceptance':False,'bit':False,'remote':False,'flash':False})
 finally:
  guard('final');k.ReleaseMutex(h);k.CloseHandle(h)
if __name__=='__main__':
 try:main()
 except BaseException:
  save('failure.json',{'traceback':traceback.format_exc(),'time':time.time(),'pid':os.getpid()});print(traceback.format_exc(),flush=True);sys.exit(1)
