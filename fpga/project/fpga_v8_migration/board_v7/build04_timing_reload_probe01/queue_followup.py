from probe import E,processes,busy,main
import time,ctypes,os,traceback
print('LOCAL_FOLLOWUP_QUEUE',os.getpid(),flush=True)
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];k.CreateMutexW.restype=ctypes.c_void_p
k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint];k.WaitForSingleObject.restype=ctypes.c_uint
k.ReleaseMutex.argtypes=[ctypes.c_void_p];k.CloseHandle.argtypes=[ctypes.c_void_p]
for label,script in [('ta_diagnostic02','ta_inventory01.tcl'),('mapped_graph01','mapped_graph01.tcl')]:
 deadline=time.time()+1200
 while time.time()<deadline:
  if (E/'probes/diagnostic_reload02/receipt.json').exists() and not busy(processes()):
   h=k.CreateMutexW(None,False,'Global\\ov56401_PDS_single_instance')
   if h:
    r=k.WaitForSingleObject(h,0)
    if r in (0,128):
     k.ReleaseMutex(h);k.CloseHandle(h)
     try:main(label,E/script)
     except BaseException:print(traceback.format_exc(),flush=True)
     break
    k.CloseHandle(h)
  time.sleep(5)
 else:print('QUEUE_DEADLINE_BLOCKED',label,flush=True);break
print('LOCAL_FOLLOWUP_DONE',flush=True)
