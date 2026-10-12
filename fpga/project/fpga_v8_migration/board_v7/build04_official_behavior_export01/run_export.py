from pathlib import Path
import ctypes, hashlib, json, shutil, subprocess, sys, time
sys.dont_write_bytecode=True
E=Path(__file__).resolve().parent; BOARD=E.parent
PDS=Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
SOURCE=BOARD/'source_diagnostics_timing_build_04/evidence/runtime/mapping60_01/isolated_mapping_work/device_map/v7_sdt_top_map.adf'
ROOTS=[BOARD/n for n in ['source_diagnostics_timing_build_04','source_diagnostics_timing_build_03','source_diagnostics_timing_build_02','diagnostic_sync_register_map02','build04_mapped_endpoint_review02','build04_mailbox_clock_review01','build04_route_prepare01']]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,o):
 p=E/n
 if p.exists(): raise RuntimeError('Refuse overwrite '+str(p))
 p.write_text(json.dumps(o,indent=2,ensure_ascii=True)+'\n',encoding='ascii')
def inventory(): return {str(p):sha(p) for r in ROOTS for p in r.rglob('*') if p.is_file()}
def idle(label):
 ps=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command','ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine) -Compress']))
 busy=[p for p in ps if p['Name'].lower() in {'pds.exe','pds_shell.exe','ta.exe'}]
 save(label+'_idle.json',{'time':time.time(),'processes':ps,'busy':busy})
 if busy: raise RuntimeError('PDS busy')
def tool(label,text):
 w=E/label; w.mkdir(); script=w/'commands.tcl'; script.write_text(text,encoding='ascii')
 cmd=[str(PDS),'-file',str(script),'-work_dir',str(w),'-project_name','behavior_'+label]
 idle(label)
 save(label+'_launch.json',{'command':cmd,'cwd':str(w),'inputs':{str(p):sha(p) for p in [PDS,script]},'mutex':'Global\\ov56401_PDS_single_instance','time':time.time()})
 print('REAL_TOOL_START '+label,flush=True)
 with (w/'shell.log').open('xb') as log:
  p=subprocess.Popen(cmd,cwd=w,stdout=log,stderr=subprocess.STDOUT)
  save(label+'_process.json',{'pid':p.pid,'time':time.time()}); code=p.wait()
 save(label+'_receipt.json',{'exit_code':code,'files':{str(p):sha(p) for p in w.rglob('*') if p.is_file()},'time':time.time()})
 print('REAL_TOOL_FINISH '+label+' exit='+str(code),flush=True)
 return w
def main():
 before=inventory();save('protection_before.json',before)
 idle('before_mutex')
 k=ctypes.WinDLL('kernel32',use_last_error=True)
 k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];k.CreateMutexW.restype=ctypes.c_void_p
 k.ReleaseMutex.argtypes=[ctypes.c_void_p];k.CloseHandle.argtypes=[ctypes.c_void_p]
 h=k.CreateMutexW(None,True,'Global\\ov56401_PDS_single_instance');exists=ctypes.get_last_error()==183
 if not h or exists:
  if h:k.CloseHandle(h)
  raise RuntimeError('Stage mutex occupied')
 try:
  idle('mutex_acquired')
  c=E/'input';c.mkdir(); copy=c/SOURCE.name;shutil.copy2(SOURCE,copy)
  assert sha(copy)==sha(SOURCE)=='3a0478381bb9761f677937bf0a55374119fc2b6ce683d847d8a1dda2aacd5419'
  save('copy_adf_binding.json',{'source':str(SOURCE),'copy':str(copy),'source_sha256':sha(SOURCE),'copy_sha256':sha(copy),'size':copy.stat().st_size})
  tool('help01','set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\nputs "COMMANDS [lsort [info commands]]"\nforeach c {.switch_db .verilog.print gen_netlist create_vlog_netlist} {puts "HELP_BEGIN $c"; puts "HELP_RESULT [catch {help $c} result] $result"; if {[llength [info commands $c]]} {puts "DASH_HELP_RESULT [catch {$c -help} result] $result"}; puts "HELP_END $c"}\n')
 finally:
  after=inventory();save('protection_after_help.json',after);save('protection_comparison_help.json',{'unchanged':before==after,'files':len(before),'copy_unchanged':sha(copy)==sha(SOURCE)})
  k.ReleaseMutex(h);k.CloseHandle(h)
if __name__=='__main__':main()
