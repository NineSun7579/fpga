import run_actual as a
from pathlib import Path
import json,ctypes,subprocess,time,sys,traceback
def main():
 a.GUARD=json.loads((a.E/'source_stage_hash_before.json').read_bytes());a.idle('target_before_mutex')
 k=ctypes.WinDLL('kernel32',use_last_error=True);k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];k.CreateMutexW.restype=ctypes.c_void_p
 k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong];k.WaitForSingleObject.restype=ctypes.c_ulong;k.ReleaseMutex.argtypes=[ctypes.c_void_p];k.CloseHandle.argtypes=[ctypes.c_void_p]
 h=k.CreateMutexW(None,False,'Global\\ov56401_PDS_single_instance');wait=k.WaitForSingleObject(h,0)
 if wait not in (0,128):k.CloseHandle(h);raise RuntimeError('Mutex busy')
 try:
  a.idle('target_acquired');pairs=json.loads((a.E/'fresh_mailbox_pairs_v2.json').read_bytes())['pairs']
  if len(pairs)!=1280:raise RuntimeError('Fresh target cardinality mismatch')
  route=a.W/'place_route/v7_sdt_top_pnr.adf';r='{'+route.as_posix()+'}';first=pairs[0]
  def lst(v):return '{'+' '.join('{'+x+'}' for x in v)+'}'
  opts='report_timing -force_to_run -input_db_file '+r+' -delay_type min_max -report_exception TRUE -input_pins TRUE -nworst 1 '
  a.tool('single_pair_actual',a.ARCH+opts+'-max_path 1024 -from '+lst([first['start']])+' -to '+lst([first['end']])+'\n',a.E/'reports/single_pair_actual')
  a.tool('mailbox1280_actual',a.ARCH+opts+'-max_path 200000 -from '+lst(sorted({x['start'] for x in pairs}))+' -to '+lst(sorted({x['end'] for x in pairs}))+'\n',a.E/'reports/mailbox1280_actual')
  a.idle('TA_disable_single')
  folder=a.E/'TA_disable_single';folder.mkdir();sdc=folder/'native_single_test.sdc'
  sdc.write_text('set_clock_groups -name {cmos1_pclk} -asynchronous -group [get_clocks {cmos1_pclk}] -disable\nset_max_delay 15.238 -from [get_pins {'+first['start']+'}] -to [get_pins {'+first['end']+'}]\n',encoding='ascii')
  tcl=folder/'inventory.tcl';tcl.write_text('puts {TA_ACTUAL_COMMANDS_BEGIN}\nputs [lsort [info commands]]\nputs {TA_ACTUAL_COMMANDS_END}\nif {[llength [info commands help]]} {help report_timing; help save_adif; help set_clock_groups}\nexit\n',encoding='ascii')
  ta=Path('C:/pango/PDS_2022.2-SP6.4/bin/ta.exe');cmd=[str(ta),str(route),'-sdc',str(sdc),'-rtr',str(folder),'-tcl',str(tcl)]
  a.save('TA_disable_single_toolcmd.json',{'argv':cmd,'tool_sha256':a.sha(ta),'sdc_sha256':a.sha(sdc),'tcl_sha256':a.sha(tcl),'scope':'Official documented -sdc interface, native exact single-pair test only; not replacement-clock/full-CDB acceptance'})
  log=a.E/'TA_disable_single.log';start=time.time()
  with log.open('xb') as f:
   p=subprocess.Popen(cmd,cwd=folder,stdout=f,stderr=subprocess.STDOUT);a.save('TA_disable_single_process.json',{'pid':p.pid,'time':start});print('REAL_TA_START pid='+str(p.pid),flush=True);rc=p.wait()
  a.save('TA_disable_single_rawreceipt.json',{'rc':rc,'start':start,'end':time.time(),'log_sha256':a.sha(log),'artifacts':a.tree(folder)});print('REAL_TA_FINISH rc='+str(rc),flush=True)
 finally:
  a.guard('targets_final');k.ReleaseMutex(h);k.CloseHandle(h)
if __name__=='__main__':
 try:main()
 except BaseException:
  a.save('target_failure.json',{'traceback':traceback.format_exc(),'time':time.time()});print(traceback.format_exc(),flush=True);sys.exit(1)
