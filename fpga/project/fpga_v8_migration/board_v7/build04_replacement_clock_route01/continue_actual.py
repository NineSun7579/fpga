import run_actual as a
import ctypes,json,traceback,sys,time
from pathlib import Path
a.GUARD=json.loads((a.E/'source_stage_hash_before.json').read_bytes())
def main():
 a.idle('continuation_before_mutex')
 k=ctypes.WinDLL('kernel32',use_last_error=True)
 k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];k.CreateMutexW.restype=ctypes.c_void_p
 k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong];k.WaitForSingleObject.restype=ctypes.c_ulong
 k.ReleaseMutex.argtypes=[ctypes.c_void_p];k.CloseHandle.argtypes=[ctypes.c_void_p]
 h=k.CreateMutexW(None,False,'Global\\ov56401_PDS_single_instance');wait=k.WaitForSingleObject(h,0)
 if wait not in (0,128):k.CloseHandle(h);raise RuntimeError('Global mutex busy')
 try:
  a.idle('continuation_acquired');route=a.W/'place_route/v7_sdt_top_pnr.adf'
  if not route.is_file() or not route.stat().st_size:raise RuntimeError('No native PNR ADF')
  a.save('route_selection_correction.json',{'route':str(route),'sha256':a.sha(route),'reason':'PNR -report_timing legitimately creates PLC, PNR and RTP ADF; select actual PNR explicitly; original collector failure preserved','pnr_rc':json.loads((a.E/'pnr_rawreceipt.json').read_bytes())['rc']})
  r='{'+route.as_posix()+'}'
  a.tool('native_graph',a.ARCH+'.switch_db -input '+r+' -output {'+(a.E/'routed_dump.txt').as_posix()+'}\n',a.E/'graph')
  a.tool('global10',a.ARCH+'report_timing -force_to_run -input_db_file '+r+' -delay_type min_max -max_path 10 -nworst 1 -input_pins TRUE -report_exception TRUE\n',a.E/'reports/global10')
  a.tool('reload_interface_help',a.ARCH+'help .switch_db\nhelp export_fdc\nhelp save_adif\nhelp set_clock_groups\nhelp delete\n',a.E/'help')
 finally:
  a.guard('continuation_final');k.ReleaseMutex(h);k.CloseHandle(h)
if __name__=='__main__':
 try:main()
 except BaseException:
  a.save('continuation_failure.json',{'traceback':traceback.format_exc(),'time':time.time()});print(traceback.format_exc());sys.exit(1)
