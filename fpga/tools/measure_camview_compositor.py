"""Temporarily disable desktop compositing, measure, and restore it."""
import shlex
import subprocess
import sys
from board_host import ssh_connect

c=ssh_connect(timeout=8)
def run(command):
    s,o,e=c.exec_command('sudo -S sh -c '+shlex.quote(command),timeout=20)
    s.write('123456\n');s.flush()
    data,err=o.read(),e.read()
    if o.channel.recv_exit_status(): raise RuntimeError(err.decode(errors='replace'))
    return data.decode().strip()
setting=None
original=None
try:
    code=("from pathlib import Path; import subprocess; "
          "pid=subprocess.check_output(['pgrep','-u','linaro','-x','xfwm4']).decode().strip(); "
          "print(next(x.split(b'=',1)[1].decode() for x in Path('/proc/'+pid+'/environ').read_bytes().split(bytes([0])) "
          "if x.startswith(b'DBUS_SESSION_BUS_ADDRESS=')))")
    bus=run('python3 -c '+shlex.quote(code))
    setting=('sudo -u linaro env DBUS_SESSION_BUS_ADDRESS='+shlex.quote(bus)+
             ' xfconf-query -c xfwm4 -p /general/use_compositing')
    original=run(setting)
    assert original in ('true','false')
    run(setting+' -s false')
    subprocess.run([sys.executable,str(__file__).replace('measure_camview_compositor.py','measure_camview_runtime.py'),
                    'uploadfirstnocompositor'],check=True)
finally:
    if setting and original in ('true','false'):
        run(setting+' -s '+original)
        print('Restored desktop compositing:',original)
    c.close()
