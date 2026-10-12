import run_export as r
import ctypes
def main():
 before=r.inventory();r.save('protection_before_export.json',before);r.idle('export_before_mutex')
 k=ctypes.WinDLL('kernel32',use_last_error=True)
 k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];k.CreateMutexW.restype=ctypes.c_void_p
 k.ReleaseMutex.argtypes=[ctypes.c_void_p];k.CloseHandle.argtypes=[ctypes.c_void_p]
 h=k.CreateMutexW(None,True,'Global\\ov56401_PDS_single_instance');exists=ctypes.get_last_error()==183
 if not h or exists:
  if h:k.CloseHandle(h)
  raise RuntimeError('Mutex busy')
 copy=r.E/'input'/r.SOURCE.name
 try:
  r.idle('export_mutex_acquired');assert r.sha(copy)==r.sha(r.SOURCE)
  r.tool('functional01','set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\ngen_netlist -force_to_run -input_db_file {'+copy.as_posix()+'} -func_sim_only -sdf_annotate FALSE\n')
 finally:
  after=r.inventory();r.save('protection_after_export.json',after);r.save('protection_comparison_export.json',{'unchanged':before==after,'files':len(before),'copy_unchanged':r.sha(copy)==r.sha(r.SOURCE)})
  k.ReleaseMutex(h);k.CloseHandle(h)
if __name__=='__main__':main()
