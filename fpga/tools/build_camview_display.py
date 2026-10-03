"""Build the display candidate without stopping the current viewer."""
from pathlib import Path
import shlex
import sys
from board_host import ssh_connect

label = sys.argv[1]
assert label.isalnum()
root = Path(__file__).resolve().parents[2]
c = ssh_connect(timeout=8)
try:
    with c.open_sftp() as transfer:
        transfer.put(str(root / 'project/host/camview/main.cpp'), '/tmp/camview_display_build.cpp')
    command = ('cp /tmp/camview_display_build.cpp /root/ov5640/camview_display_optimized/main.cpp; '
               'cd /root/ov5640/camview_display_optimized && make -j2')
    s,o,e = c.exec_command('sudo -S sh -c ' + shlex.quote(command), timeout=90)
    s.write('123456\n'); s.flush()
    data = o.read() + e.read()
    (root / 'log/camview_fps_audit_20261003' / (label + '_build.log')).write_bytes(data)
    print(data.decode(errors='replace'))
    if o.channel.recv_exit_status(): raise RuntimeError('Build failed')
finally:
    c.close()
