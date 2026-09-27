#!/usr/bin/env python3
"""rb.py -- run one sudo bash command on the board over SSH.

    python tools/rb.py '<shell command>'

Prints stdout+stderr and the remote exit code.
"""
import shlex
import sys

from board_host import ssh_connect

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
cmd = sys.argv[1] if len(sys.argv) > 1 else 'true'
c = ssh_connect()
try:
    i, o, e = c.exec_command('sudo -S -p "" bash -c ' + shlex.quote(cmd), timeout=3600)
    i.write('123456\n')
    i.flush()
    out = o.read().decode('utf-8', 'replace')
    err = e.read().decode('utf-8', 'replace')
    rc = o.channel.recv_exit_status()
    print(out, end='')
    if err.strip():
        print(err, end='')
    print('\n[rc=%d]' % rc)
finally:
    c.close()
