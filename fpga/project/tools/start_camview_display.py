"""Gracefully restart display candidate with an optional texture ring."""
import shlex
import re
import sys
import time
from board_host import ssh_connect

swap_interval = next((int(arg.split('=', 1)[1]) for arg in sys.argv[1:] if arg.startswith('--swap-interval=')), None)
assert swap_interval is None or swap_interval in (0, 1)
sys.argv = [arg for arg in sys.argv if not arg.startswith('--swap-interval=')]
ring=int(sys.argv[1]) if len(sys.argv)>1 else 1
idle = int(sys.argv[2]) if len(sys.argv)>2 else None
bypass = len(sys.argv)>3 and sys.argv[3]=='bypass'
offscreen = len(sys.argv)>3 and sys.argv[3] in ('offscreen','swapdriven')
swapdriven = len(sys.argv)>3 and sys.argv[3]=='swapdriven'
assert ring in (1,2,3)
assert idle is None or idle in (0,5)
c=ssh_connect(timeout=8)
def run(command):
    s,o,e=c.exec_command('sudo -S sh -c '+shlex.quote(command),timeout=20)
    s.write('123456\n');s.flush()
    data,err=o.read(),e.read()
    if o.channel.recv_exit_status(): raise RuntimeError(err.decode(errors='replace'))
    return data
try:
    owners=run('fuser /dev/pango_pci_driver 2>/dev/null || true').decode().split()
    for pid in owners:
        name=run('cat /proc/'+pid+'/comm').decode().strip()
        assert name=='camview', 'DMA device owned by '+name
    code='''import ctypes as c,re,subprocess
x=c.CDLL('libX11.so.6');t=c.CDLL('libXtst.so.6')
x.XOpenDisplay.argtypes=[c.c_char_p];x.XOpenDisplay.restype=c.c_void_p
x.XKeysymToKeycode.argtypes=[c.c_void_p,c.c_ulong];x.XKeysymToKeycode.restype=c.c_uint
x.XSetInputFocus.argtypes=[c.c_void_p,c.c_ulong,c.c_int,c.c_ulong]
x.XFlush.argtypes=[c.c_void_p];x.XCloseDisplay.argtypes=[c.c_void_p]
t.XTestFakeKeyEvent.argtypes=[c.c_void_p,c.c_uint,c.c_int,c.c_ulong]
d=x.XOpenDisplay(b':0');assert d
tree=subprocess.check_output(['xwininfo','-root','-tree']).decode()
m=re.search(r'(0x[0-9a-f]+) "camview  QUAD THREAD VIEW"',tree)
if m:
 x.XSetInputFocus(d,int(m[1],16),2,0)
 key=x.XKeysymToKeycode(d,ord('q'))
 t.XTestFakeKeyEvent(d,key,1,0);t.XTestFakeKeyEvent(d,key,0,0);x.XFlush(d)
x.XCloseDisplay(d)
'''
    if owners:
        run('DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 python3 -c '+shlex.quote(code))
        time.sleep(3)
    assert not run('pgrep -x camview || true').strip(), 'Viewer has not exited'
    run('nohup sh -c '+shlex.quote('cd /root/ov5640/camview_display_optimized && '
        'DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 CAMVIEW_TEXTURE_RING='+str(ring)+
        (' QT_QPA_UPDATE_IDLE_TIME='+str(idle) if idle is not None else '')+
        (' CAMVIEW_OFFSCREEN_DRAW=1' if offscreen else '')+
         (' CAMVIEW_SWAP_DRIVEN=1' if swapdriven else '')+
         (' CAMVIEW_SWAP_INTERVAL='+str(swap_interval) if swap_interval is not None else '')+' exec ./camview')+
        ' > /root/ov5640/camview_fps_candidate.log 2>&1 </dev/null &')
    print('Started display candidate, texture ring',ring)
    if bypass:
        time.sleep(2)
        tree=run('DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 xwininfo -root -tree').decode()
        window=re.search(r'(0x[0-9a-f]+) "camview  QUAD THREAD VIEW"',tree)
        assert window, 'Viewer window not found'
        run('DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 xprop -id '+window.group(1)+
            ' -f _NET_WM_BYPASS_COMPOSITOR 32c -set _NET_WM_BYPASS_COMPOSITOR 1')
finally:
    c.close()
