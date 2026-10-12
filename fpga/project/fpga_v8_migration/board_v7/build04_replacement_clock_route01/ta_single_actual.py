from pathlib import Path
import json,ctypes,subprocess,time,sys,traceback
import run_actual as a
def main():
 a.GUARD=json.loads((a.E/'source_stage_hash_before.json').read_bytes());a.idle('ta_single_before_mutex')
 k=ctypes.WinDLL('kernel32',use_last_error=True);k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];k.CreateMutexW.restype=ctypes.c_void_p
 k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong];k.WaitForSingleObject.restype=ctypes.c_ulong;k.ReleaseMutex.argtypes=[ctypes.c_void_p];k.CloseHandle.argtypes=[ctypes.c_void_p]
 h=k.CreateMutexW(None,False,'Global\\ov56401_PDS_single_instance');wait=k.WaitForSingleObject(h,0)
 if wait not in (0,128):k.CloseHandle(h);raise RuntimeError('Global mutex busy')
 try:
  a.idle('ta_single_acquired');folder=a.E/'TA_native_single_actual';folder.mkdir()
  pair=json.loads((a.E/'fresh_mailbox_pairs_v2.json').read_bytes())['pairs'][0]
  sdc=folder/'native_three_clock_single.sdc'
  sdc.write_text('create_clock -name {free_clk} [get_ports {free_clk}] -period 40.000 -waveform {0.000 20.000}\ncreate_clock -name {cmos1_pclk} [get_ports {cmos1_pclk}] -period 11.905 -waveform {0.000 5.952}\nset_clock_uncertainty 0.002 [get_clocks {cmos1_pclk}] -setup -hold\ncreate_generated_clock -name {ddrphy_sysclk} -source [get_ports {free_clk}] [get_pins {ddr3/u_ddrphy_top/ddrphy_gpll/u_gpll/gpll_inst/CLKOUT0}] -master_clock [get_clocks {free_clk}] -multiply_by 84 -divide_by 16\nset_max_delay 15.238 -from [get_pins {'+pair['start']+'}] -to [get_pins {'+pair['end']+'}]\n',encoding='ascii')
  tcl=folder/'report_single.tcl';tcl.write_text('report_timing -delay_type min_max -nworst 2 -max_path 10 -report_exception TRUE -input_pins TRUE -from {{'+pair['start']+'}} -to {{'+pair['end']+'}}\nexit\n',encoding='ascii')
  route=a.W/'place_route/v7_sdt_top_pnr.adf';ta=Path('C:/pango/PDS_2022.2-SP6.4/bin/ta.exe')
  cmd=[str(ta),'-sdc',str(sdc),'-rtr',str(folder),'-tcl',str(tcl),str(route)]
  a.save('TA_native_single_actual_toolcmd.json',{'argv':cmd,'tool_sha256':a.sha(ta),'sdc_sha256':a.sha(sdc),'script_sha256':a.sha(tcl),'route_sha256':a.sha(route),'scope':'Actual single-pair STA with native exact pins and three relevant replacement clocks; not full replacement CDB/PNR acceptance; no save_adif exists in TA'})
  start=time.time();log=a.E/'TA_native_single_actual.log'
  with log.open('xb') as f:
   p=subprocess.Popen(cmd,cwd=folder,stdout=f,stderr=subprocess.STDOUT);a.save('TA_native_single_actual_process.json',{'pid':p.pid,'time':start});print('REAL_NATIVE_SINGLE_TA_START',p.pid,flush=True);rc=p.wait()
  a.save('TA_native_single_actual_rawreceipt.json',{'rc':rc,'start':start,'end':time.time(),'log_sha256':a.sha(log),'artifacts':a.tree(folder)});print('REAL_NATIVE_SINGLE_TA_FINISH',rc,flush=True)
 finally:
  a.guard('ta_single_final');k.ReleaseMutex(h);k.CloseHandle(h)
if __name__=='__main__':
 try:main()
 except BaseException:
  a.save('ta_single_failure.json',{'traceback':traceback.format_exc(),'time':time.time()});print(traceback.format_exc(),flush=True);sys.exit(1)
