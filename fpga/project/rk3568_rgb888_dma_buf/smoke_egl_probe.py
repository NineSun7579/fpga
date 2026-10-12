import shlex,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
p=Path(__file__).resolve().parent/'egl_probe_build_1791618116956610000'
m=json.loads((p/'manifest.json').read_text())
code='''import ctypes
e=ctypes.CDLL(None)
e.eglGetProcAddress.restype=ctypes.c_void_p
assert e.eglGetProcAddress(b"eglSwapBuffers")
e.eglSwapInterval.argtypes=[ctypes.c_void_p,ctypes.c_int]
print("invalid_display_result",e.eglSwapInterval(None,0))
'''
c=board_ssh.connect()
try:
    rc,o,e=board_ssh.run(c,'env DETVIEW_EGL_SWAP_PROBE=1 LD_PRELOAD='+shlex.quote(m['library'])+' python3 -c '+shlex.quote(code),timeout=20,sudo=True)
    (p/'smoke.log').write_text(o+e);print(o+e)
    assert rc==0 and 'interval_request=0' in e
finally:c.close()
