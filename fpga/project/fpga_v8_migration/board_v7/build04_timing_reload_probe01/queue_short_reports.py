from probe import E,processes,busy,main
import time,ctypes,os,json,traceback
print('LOCAL_SHORT_REPORT_QUEUE',os.getpid(),flush=True)
deadline=time.time()+1200
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];k.CreateMutexW.restype=ctypes.c_void_p
k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint];k.WaitForSingleObject.restype=ctypes.c_uint
k.ReleaseMutex.argtypes=[ctypes.c_void_p];k.CloseHandle.argtypes=[ctypes.c_void_p]
while time.time()<deadline:
 ps=processes()
 if not busy(ps):
  h=k.CreateMutexW(None,False,'Global\\ov56401_PDS_single_instance')
  if h:
   r=k.WaitForSingleObject(h,0)
   if r in (0,128):
    k.ReleaseMutex(h);k.CloseHandle(h)
    try:
     main('diagnostic_reload02',E/'diagnostic_reload01.tcl')
     print('LOCAL_SHORT_REPORT_DONE',flush=True);break
    except BaseException:
     print(traceback.format_exc(),flush=True);break
   k.CloseHandle(h)
 time.sleep(5)
else:print('QUEUE_DEADLINE_BLOCKED_NO_TOOL_STARTED',flush=True)
