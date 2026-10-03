"""Exercise paused-upload zero reporting on X11 and always resume viewer."""
from pathlib import Path
import shlex
import time
from board_host import ssh_connect

ROOT = Path(__file__).resolve().parents[2]
out = ROOT / 'log/camview_fps_audit_20261003'
code = '''import ctypes as c
import re, subprocess
x=c.CDLL('libX11.so.6'); t=c.CDLL('libXtst.so.6')
x.XOpenDisplay.argtypes=[c.c_char_p]; x.XOpenDisplay.restype=c.c_void_p
x.XKeysymToKeycode.argtypes=[c.c_void_p,c.c_ulong]; x.XKeysymToKeycode.restype=c.c_uint
x.XSetInputFocus.argtypes=[c.c_void_p,c.c_ulong,c.c_int,c.c_ulong]
x.XFlush.argtypes=[c.c_void_p]; x.XCloseDisplay.argtypes=[c.c_void_p]
t.XTestFakeKeyEvent.argtypes=[c.c_void_p,c.c_uint,c.c_int,c.c_ulong]
d=x.XOpenDisplay(b':0'); assert d
tree=subprocess.check_output(['xwininfo','-root','-tree']).decode()
match=re.search(r'(0x[0-9a-f]+) "camview  QUAD THREAD VIEW"',tree); assert match
x.XSetInputFocus(d,int(match[1],16),2,0)
key=x.XKeysymToKeycode(d,ord('p'))
t.XTestFakeKeyEvent(d,key,1,0); t.XTestFakeKeyEvent(d,key,0,0)
x.XFlush(d); x.XCloseDisplay(d)
'''
c = ssh_connect(timeout=8)
def run(command):
    s,o,e=c.exec_command('sudo -S sh -c '+shlex.quote(command),timeout=20)
    s.write('123456\n');s.flush()
    data,err=o.read(),e.read()
    if o.channel.recv_exit_status(): raise RuntimeError(err.decode(errors='replace'))
    return data
toggle = 'DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 python3 -c '+shlex.quote(code)
paused=False
try:
    run(toggle); paused=True
    time.sleep(12)
    data=run('tail -n 200 /root/ov5640/camview_fps_candidate.log')
    (out / 'fpsfix_pause.txt').write_bytes(data)
    assert b'uploaded_fps=0.000' in data
    for camera in range(1,7):
        assert f'upload camera={camera} fps=0.000'.encode() in data
    print('PASS: all six upload rates reach zero while paused')
finally:
    if paused: run(toggle)
    c.close()
