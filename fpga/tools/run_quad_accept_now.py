#!/usr/bin/env python3
"""Run the quad acceptance capture on the already-programmed board and pull evidence."""
import shlex
import subprocess
import sys
from pathlib import Path

import paramiko

from board_host import board_host

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tp' / 'quad_accept'
OUT.mkdir(parents=True, exist_ok=True)
PY = sys.executable
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(board_host(), username='linaro', password='123456', allow_agent=False, look_for_keys=False, timeout=15)


def sh(cmd, timeout=900, check=True):
    i, o, e = c.exec_command('sudo -S -p "" bash -c ' + shlex.quote(cmd), timeout=timeout)
    i.write('123456\n'); i.flush()
    text = o.read().decode('utf-8', 'replace') + e.read().decode('utf-8', 'replace')
    rc = o.channel.recv_exit_status()
    print('$ ' + cmd + '\n' + text, flush=True)
    with (OUT / 'session.log').open('a', encoding='utf-8') as f:
        f.write('$ ' + cmd + '\n' + text + '\n')
    if check and rc:
        print('WARN remote rc=%d' % rc)
    return rc, text


try:
    sh('pkill -9 -x run_camview.sh || true; pkill -9 -x camview || true; pkill -9 -x detview || true; sleep 1; '
       'ls -l /sys/bus/pci/devices/0002:21:00.0/driver && echo BOUND', check=False)
    s = c.open_sftp()
    for f in ('cam3_i2c_pt.py', 'quad_accept_board.py'):
        s.put(str(ROOT / 'tools' / f), '/tmp/' + f)
    sh('rm -rf /tmp/quad_accept', check=False)
    sh('python3 -u /tmp/quad_accept_board.py', check=False)
    for f in s.listdir('/tmp/quad_accept'):
        try:
            s.get('/tmp/quad_accept/' + f, str(OUT / f))
            print('pulled', f, (OUT / f).stat().st_size, 'bytes')
        except Exception as ex:
            print('pull skip', f, ex)
    s.close()
finally:
    c.close()

print('\n--- local analysis ---', flush=True)
subprocess.run([PY, str(ROOT / 'tools' / 'analyze_quad_evidence.py'), str(OUT)])
