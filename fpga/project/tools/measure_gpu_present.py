"""Reversible EGL timing comparisons for the existing display candidate."""
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
from board_host import ssh_connect

MODE = sys.argv[1]
assert MODE in ('baseline', 'compositor_off', 'swap0')
ROOT = Path(__file__).resolve().parents[2]
cli = ssh_connect()

def run(command, timeout=20):
    stdin, stdout, stderr = cli.exec_command('sudo -S sh -c ' + shlex.quote(command), timeout=timeout)
    stdin.write('123456\n'); stdin.flush()
    data, error = stdout.read(), stderr.read()
    if stdout.channel.recv_exit_status():
        raise RuntimeError(error.decode(errors='replace'))
    return data.decode(errors='replace')

QUIT = '''import ctypes as c,re,subprocess
x=c.CDLL('libX11.so.6');t=c.CDLL('libXtst.so.6')
x.XOpenDisplay.argtypes=[c.c_char_p];x.XOpenDisplay.restype=c.c_void_p
x.XKeysymToKeycode.argtypes=[c.c_void_p,c.c_ulong];x.XKeysymToKeycode.restype=c.c_uint
x.XSetInputFocus.argtypes=[c.c_void_p,c.c_ulong,c.c_int,c.c_ulong]
x.XFlush.argtypes=[c.c_void_p];x.XCloseDisplay.argtypes=[c.c_void_p]
t.XTestFakeKeyEvent.argtypes=[c.c_void_p,c.c_uint,c.c_int,c.c_ulong]
d=x.XOpenDisplay(b':0');assert d
tree=subprocess.check_output(['xwininfo','-root','-tree']).decode()
m=re.search(r'(0x[0-9a-f]+) "camview  QUAD THREAD VIEW"',tree)
assert m, 'Viewer window missing'
x.XSetInputFocus(d,int(m[1],16),2,0)
key=x.XKeysymToKeycode(d,ord('q'))
t.XTestFakeKeyEvent(d,key,1,0);t.XTestFakeKeyEvent(d,key,0,0);x.XFlush(d);x.XCloseDisplay(d)
'''
original = setting = None
changed = False
result = {'mode': MODE}
try:
    owners = run('fuser /dev/pango_pci_driver 2>/dev/null || true').split()
    assert len(owners) == 1 and run('cat /proc/' + owners[0] + '/comm').strip() == 'camview'
    assert run('readlink /proc/' + owners[0] + '/cwd').strip() == '/root/ov5640/camview_display_optimized'
    buscode = "from pathlib import Path; import subprocess; p=subprocess.check_output(['pgrep','-u','linaro','-x','xfwm4']).decode().strip(); print(next(x.split(b'=',1)[1].decode() for x in Path('/proc/'+p+'/environ').read_bytes().split(bytes([0])) if x.startswith(b'DBUS_SESSION_BUS_ADDRESS=')))"
    bus = run('python3 -c ' + shlex.quote(buscode)).strip()
    setting = 'sudo -u linaro env DBUS_SESSION_BUS_ADDRESS=' + shlex.quote(bus) + ' xfconf-query -c xfwm4 -p /general/use_compositing'
    original = run(setting).strip()
    assert original == 'true', 'Comparison expects the current composited baseline'
    source = Path(__file__).with_name('gpu_present_timing.c').read_text()
    writecode = 'from pathlib import Path; Path("/tmp/ov5640_gpu_present_timing.c").write_text(' + repr(source) + ')'
    run('python3 -c ' + shlex.quote(writecode))
    run('gcc -shared -fPIC -O2 -Wall /tmp/ov5640_gpu_present_timing.c -o /tmp/ov5640_gpu_present_timing.so -ldl')
    smoke = Path(__file__).with_name('probe_rk_gpu_egl.py').read_text()
    run('DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 LD_PRELOAD=/tmp/ov5640_gpu_present_timing.so python3 -c ' + shlex.quote(smoke))
    run('DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 python3 -c ' + shlex.quote(QUIT))
    changed = True
    for _ in range(30):
        if not run('pgrep -x camview || true').strip(): break
        time.sleep(0.2)
    assert not run('pgrep -x camview || true').strip(), 'Viewer did not exit'
    if MODE == 'compositor_off': run(setting + ' -s false')
    env = 'DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 CAMVIEW_TEXTURE_RING=1 LD_PRELOAD=/tmp/ov5640_gpu_present_timing.so'
    if MODE == 'swap0': env += ' CAMVIEW_SWAP_INTERVAL=0'
    logfile = '/tmp/ov5640_gpu_present_' + MODE + '.log'
    run('nohup sh -c ' + shlex.quote('cd /root/ov5640/camview_display_optimized && ' + env + ' exec ./camview') + ' > ' + logfile + ' 2>&1 </dev/null &')
    time.sleep(5)
    assert run('pgrep -x camview').strip(), 'Instrumented viewer failed'
    result['before'] = run("cat /proc/uptime; grep -c 'flip timeout' /var/log/Xorg.0.log")
    time.sleep(20)
    result['after'] = run("cat /proc/uptime; grep -c 'flip timeout' /var/log/Xorg.0.log; cat /sys/devices/platform/fde60000.gpu/utilisation")
    result['log'] = run('cat ' + logfile)
    (ROOT / 'log' / ('rk3568_gpu_present_' + MODE + '.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
    for line in result['log'].splitlines():
        if re.match(r'(gpu_timing|uploaded_fps|paint_ms|camera_upload_ms|camera_draw_ms)', line): print(line)
    print('Before:', result['before'], 'After:', result['after'])
finally:
    if setting and original in ('true', 'false'): run(setting + ' -s ' + original)
    cli.close()
    if changed:
        subprocess.run([sys.executable, str(Path(__file__).with_name('start_camview_display.py')), '1'], check=True)
        print('Restored viewer without timing hook and original compositing')
