import run_export as r
import ctypes
import sys
def main():
 label=sys.argv[1] if len(sys.argv)>1 else 'native01'
 before=r.inventory();r.save('protection_before_'+label+'.json',before);r.idle(label+'_before_mutex')
 k=ctypes.WinDLL('kernel32',use_last_error=True)
 k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];k.CreateMutexW.restype=ctypes.c_void_p
 k.ReleaseMutex.argtypes=[ctypes.c_void_p];k.CloseHandle.argtypes=[ctypes.c_void_p]
 h=k.CreateMutexW(None,True,'Global\\ov56401_PDS_single_instance');exists=ctypes.get_last_error()==183
 if not h or exists:
  if h:k.CloseHandle(h)
  raise RuntimeError('Mutex busy')
 copy=r.E/'input'/r.SOURCE.name
 try:
  r.idle(label+'_mutex_acquired');assert r.sha(copy)==r.sha(r.SOURCE)
  out=r.E/label/'mapped_dump.txt'
  r.tool(label,'set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n.switch_db -input {'+copy.as_posix()+'} -output {'+out.as_posix()+'}\n')
 finally:
  after=r.inventory();r.save('protection_after_'+label+'.json',after);r.save('protection_comparison_'+label+'.json',{'unchanged':before==after,'files':len(before),'copy_unchanged':r.sha(copy)==r.sha(r.SOURCE)})
  k.ReleaseMutex(h);k.CloseHandle(h)
if __name__=='__main__':main()
